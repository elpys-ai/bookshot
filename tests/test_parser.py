import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pytest

from bookparser import looks_like_author, parse_books, parse_line


@pytest.mark.parametrize("line,title,author", [
    ("«Мастер и Маргарита» — Михаил Булгаков", "Мастер и Маргарита", "Михаил Булгаков"),
    ("1. Atomic Habits — James Clear", "Atomic Habits", "Джеймс Клир"),
    ("Sapiens by Yuval Noah Harari", "Sapiens", "Юваль Ной Харари"),
    ("Оруэлл - 1984", "1984", "Джордж Оруэлл"),
    ("Агата Кристи, Убийство в Восточном экспрессе", "Убийство в Восточном экспрессе", "Агата Кристи"),
    ("Мыслить медленно... решать быстро, Даниэль Канеман", "Мыслить медленно... решать быстро", "Даниэль Канеман"),
    ("• «Дюна» — Фрэнк Герберт", "Дюна", "Фрэнк Герберт"),
])
def test_parse_line(line, title, author):
    c = parse_line(line)
    assert c is not None
    assert (c.title, c.author) == (title, author)


def test_quoted_title_without_author():
    c = parse_line("«Бесы»")
    assert c.title == "Бесы" and c.author == "Автор не указан"


def test_known_author_resolves_ambiguity():
    # обе половины похожи на имя — справочник решает, кто автор
    c = parse_line("Достоевский — Идиот")
    assert (c.title, c.author) == ("Идиот", "Фёдор Достоевский")


@pytest.mark.parametrize("line", ["", "ok", "12:45", "https://t.me/books", "@bookclub", "Девочки, держите подборку на осень:"])
def test_noise_ignored(line):
    assert parse_line(line) is None


def test_genre_guess_from_known_author():
    assert parse_line("«1984» — Джордж Оруэлл").genre == "Антиутопия"
    assert parse_line("«Что-то» — Неизвестный Автор").genre == "Другое"


def test_dedup_and_order():
    books = parse_books("«Дюна» — Фрэнк Герберт\n«Дюна» — Фрэнк Герберт\nАтлант расправил плечи — Айн Рэнд")
    assert [b.title for b in books] == ["Дюна", "Атлант расправил плечи"]


def test_looks_like_author():
    assert looks_like_author("Михаил Булгаков")
    assert looks_like_author("J. K. Rowling")
    assert not looks_like_author("Мастер и Маргарита")
    assert not looks_like_author("1984")


def test_wrapped_lines_are_joined():
    text = (
        "«451 градус по Фаренгейту» — Рэй\nБрэдбери\n\n"
        "Мыслить медленно... решать быстро,\nДаниэль Канеман\n\n"
        "Агата Кристи, Убийство в Восточном\nэкспрессе\n"
    )
    got = [(b.title, b.author) for b in parse_books(text)]
    assert got == [
        ("451 градус по Фаренгейту", "Рэй Брэдбери"),
        ("Мыслить медленно... решать быстро", "Даниэль Канеман"),
        ("Убийство в Восточном экспрессе", "Агата Кристи"),
    ]
