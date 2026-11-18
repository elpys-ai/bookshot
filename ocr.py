"""Распознавание текста на скриншоте через Tesseract."""
from __future__ import annotations

import shutil

from PIL import Image, ImageOps


def ocr_available() -> bool:
    return shutil.which("tesseract") is not None


def extract_text(path: str) -> str:
    if not ocr_available():
        return ""
    import pytesseract

    img = ImageOps.exif_transpose(Image.open(path)).convert("L")
    if img.width < 1200:  # мелкий текст читается заметно лучше после увеличения
        k = 1200 / img.width
        img = img.resize((int(img.width * k), int(img.height * k)), Image.LANCZOS)
    try:
        langs = set(pytesseract.get_languages(config=""))
        lang = "rus+eng" if {"rus", "eng"} <= langs else "eng"
        return pytesseract.image_to_string(img, lang=lang, config="--psm 6")
    except Exception as exc:  # noqa: BLE001 — OCR не должен ронять приложение
        return f"[ошибка OCR: {exc}]"
