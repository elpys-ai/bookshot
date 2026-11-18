"""Рисует учебные «скриншоты» с рекомендациями книг (samples/*.png) для демо и тестов.

Это не настоящие скриншоты чужих постов — только текст-заглушки с названиями книг.
"""
import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

FONT = "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"
BOLD = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"

SAMPLES = {
    "telegram_chat.png": {
        "bg": "#e7ebf0", "head": "#527da3", "title": "Книжный клуб",
        "bubbles": [
            ("Лена", "Девочки, держите подборку на осень:"),
            ("Лена", "«Мастер и Маргарита» — Михаил Булгаков\n«1984» — Джордж Оруэлл\n«451 градус по Фаренгейту» — Рэй Брэдбери"),
            ("Аня", "Ещё советую психологию:\n«Человек в поисках смысла» — Виктор Франкл\nМыслить медленно... решать быстро, Даниэль Канеман"),
        ],
    },
    "instagram_post.png": {
        "bg": "#ffffff", "head": "#c13584", "title": "bookish.reads",
        "bubbles": [
            ("", "5 книг, которые изменят привычки 📖"),
            ("", "1. Atomic Habits — James Clear\n2. Sapiens by Yuval Noah Harari\n3. How to Win Friends and Influence People, Dale Carnegie\n4. Дейл Карнеги - Как перестать беспокоиться"),
        ],
    },
    "notes_list.png": {
        "bg": "#fff8dc", "head": "#e0a800", "title": "Заметки: прочитать",
        "bubbles": [
            ("", "Достоевский — Идиот\nТолкин - Властелин колец\nАгата Кристи, Убийство в Восточном экспрессе\nПелевин — Generation П"),
        ],
    },
}


def wrap(draw, text, font, width):
    lines = []
    for para in text.split("\n"):
        cur = ""
        for word in para.split(" "):
            test = f"{cur} {word}".strip()
            if draw.textlength(test, font=font) <= width:
                cur = test
            else:
                lines.append(cur)
                cur = word
        lines.append(cur)
    return lines


def render(spec, path: Path, w=1080):
    f, fb, fs = (ImageFont.truetype(FONT, 38), ImageFont.truetype(BOLD, 40), ImageFont.truetype(BOLD, 30))
    probe = ImageDraw.Draw(Image.new("RGB", (w, 10)))
    blocks = []
    for who, text in spec["bubbles"]:
        lines = wrap(probe, text, f, w - 180)
        blocks.append((who, lines, 40 + len(lines) * 52 + (36 if who else 0)))
    h = 150 + sum(b[2] + 28 for b in blocks) + 60
    img = Image.new("RGB", (w, h), spec["bg"])
    d = ImageDraw.Draw(img)
    d.rectangle([0, 0, w, 110], fill=spec["head"])
    d.text((40, 32), spec["title"], font=fb, fill="white")
    y = 140
    for who, lines, bh in blocks:
        d.rounded_rectangle([40, y, w - 40, y + bh], radius=28, fill="#ffffff" if spec["bg"] != "#ffffff" else "#f2f2f2")
        ty = y + 20
        if who:
            d.text((70, ty), who, font=fs, fill=spec["head"])
            ty += 40
        for ln in lines:
            d.text((70, ty), ln, font=f, fill="#111111")
            ty += 52
        y += bh + 28
    img.save(path)


if __name__ == "__main__":
    out = Path(sys.argv[1] if len(sys.argv) > 1 else "samples")
    out.mkdir(exist_ok=True)
    for name, spec in SAMPLES.items():
        render(spec, out / name)
        print("created", out / name)
