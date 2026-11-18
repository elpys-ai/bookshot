"""Разбор текста со скриншота в список книг (название + автор).

Скриншоты с рекомендациями обычно выглядят так:
    «Мастер и Маргарита» — Михаил Булгаков
    1. Atomic Habits, James Clear
    Оруэлл - 1984
    Sapiens by Yuval Noah Harari
Парсер намеренно простой и эвристический. Всё, что он угадал неверно,
пользователь исправляет на экране проверки перед сохранением.
"""
from __future__ import annotations

import re
from dataclasses import dataclass

from genres import UNKNOWN_AUTHOR, guess, lookup_author

QUOTES = "«»\"“”„'`"
BULLET = re.compile(r"^\s*(?:\d{1,2}\s*[.)]|[-•*·●▪►>])\s*")
NOISE = re.compile(r"(https?://|www\.|@\w|\b\d{1,2}:\d{2}\b|#\w)", re.I)
QUOTED = re.compile(r"[«\"“„](.+?)[»\"”“]")
# порядок важен: сначала длинные разделители
SEPARATORS = [r"\s+[—–]\s+", r"\s*[—–]\s*", r"\s+-\s+", r"\s+by\s+", r"\s+от\s+", r"\s*,\s+"]
NAME_TOKEN = re.compile(r"^(?:[A-ZА-ЯЁ][a-zа-яё]+(?:-[A-ZА-ЯЁ][a-zа-яё]+)?|[A-ZА-ЯЁ]\.)$")


@dataclass
class Candidate:
    title: str
    author: str
    genre: str


def looks_like_author(text: str) -> bool:
    """«Михаил Булгаков», «Булгаков М. А.», «J. K. Rowling» — да; «Мастер и Маргарита» — нет."""
    text = text.strip(" .,:;" + QUOTES)
    tokens = text.split()
    if not 1 <= len(tokens) <= 4 or any(ch.isdigit() for ch in text):
        return False
    if lookup_author(text):
        return True
    return all(NAME_TOKEN.match(t) for t in tokens)


def _clean_title(text: str) -> str:
    return re.sub(r"\s+", " ", text.strip(" \t.,:;" + QUOTES)).strip()


def _normalize_author(raw: str) -> str:
    raw = re.sub(r"\s+", " ", raw.strip(" \t.,:;" + QUOTES))
    hit = lookup_author(raw)
    return hit[0] if hit else raw


def parse_line(line: str) -> Candidate | None:
    line = BULLET.sub("", line.strip())
    if line.endswith(":") or len(line) < 3 or len(line) > 140 or NOISE.search(line) or not re.search(r"[A-Za-zА-Яа-яЁё]{2}", line):
        return None

    title = author = None

    # 1) название в кавычках — самый надёжный сигнал
    m = QUOTED.search(line)
    if m:
        title = _clean_title(m.group(1))
        rest = (line[: m.start()] + " " + line[m.end():]).strip()
        rest = re.sub(r"^[\s—–,:-]+|[\s—–,:-]+$", "", re.sub(r"\bby\b|\bот\b", " ", rest, flags=re.I))
        if rest and looks_like_author(rest):
            author = _normalize_author(rest)
    else:
        # 2) «A — B»: выясняем, какая половина — автор
        for sep in SEPARATORS:
            parts = re.split(sep, line, maxsplit=1)
            if len(parts) != 2 or not parts[0].strip() or not parts[1].strip():
                continue
            left, right = parts[0].strip(), parts[1].strip()
            la, ra = looks_like_author(left), looks_like_author(right)
            if sep.strip() == ",":
                # запятая — слабый разделитель: «Название, Автор» или «Имя Фамилия, Название».
                # Одиночное неизвестное слово слева («Девочки, держите…») автором не считаем.
                left_ok = la and (len(left.split()) > 1 or lookup_author(left))
                if not (ra or left_ok):
                    continue
                if la and not left_ok:
                    la = False
            if la and not ra:
                author, title = left, right
            elif ra and not la:
                title, author = left, right
            elif la and ra:
                # обе половины похожи на имя: решает справочник, иначе «Название — Автор»
                if lookup_author(left) and not lookup_author(right):
                    author, title = left, right
                else:
                    title, author = left, right
            else:
                continue
            title, author = _clean_title(title), _normalize_author(author)
            break

    if not title:
        return None
    author = author or UNKNOWN_AUTHOR
    return Candidate(title=title, author=author, genre=guess(author))


def _continues(cur: str, nxt: str) -> bool:
    """Скриншот переносит длинную строку — решаем, продолжает ли nxt строку cur."""
    cur, nxt = cur.rstrip(), nxt.strip()
    if not cur or not nxt:
        return False
    if re.search(r"(?:[,—–-]|\bby|\bот)$", cur, re.I) or cur.count("«") > cur.count("»"):
        return True
    if nxt[0].islower():
        return True
    # «… — Виктор» + «Франкл»: у автора не хватает фамилии
    if looks_like_author(nxt) and len(nxt.split()) <= 2 and not re.search("|".join(SEPARATORS), nxt):
        cand = parse_line(cur)
        return bool(cand and cand.author != UNKNOWN_AUTHOR and len(cand.author.split()) == 1)
    return False


def join_wrapped(lines: list[str]) -> list[str]:
    out: list[str] = []
    for line in lines:
        if out and _continues(out[-1], line):
            out[-1] = f"{out[-1].rstrip()} {line.strip()}"
        else:
            out.append(line)
    return out


def parse_books(text: str) -> list[Candidate]:
    seen, result = set(), []
    for line in join_wrapped(text.splitlines()):
        cand = parse_line(line)
        if not cand:
            continue
        key = (cand.title.lower(), cand.author.lower())
        if key not in seen:
            seen.add(key)
            result.append(cand)
    return result
