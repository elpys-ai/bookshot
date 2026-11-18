"""Запускает приложение во временной папке и снимает скриншоты для README (docs/screenshots).

Нужно: pip install playwright, а также Chrome/Chromium. Путь к браузеру: CHROME_PATH
(по умолчанию ищем google-chrome / chromium в PATH, иначе используется встроенный в playwright).
"""
import os
import shutil
import subprocess
import sys
import tempfile
import time
import urllib.request
from pathlib import Path

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "docs" / "screenshots"
PORT = 5057
URL = f"http://127.0.0.1:{PORT}"


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    data = tempfile.mkdtemp(prefix="shelfie-demo-")
    env = {**os.environ, "SHELFIE_DATA": data, "PORT": str(PORT)}
    server = subprocess.Popen([sys.executable, str(ROOT / "app.py")], cwd=ROOT, env=env,
                              stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    try:
        for _ in range(50):
            try:
                urllib.request.urlopen(URL, timeout=1)
                break
            except Exception:
                time.sleep(0.2)
        chrome = os.environ.get("CHROME_PATH") or shutil.which("google-chrome") or shutil.which("chromium")
        with sync_playwright() as p:
            browser = p.chromium.launch(executable_path=chrome, args=["--no-sandbox"]) if chrome else p.chromium.launch()
            page = browser.new_page(viewport={"width": 1100, "height": 1250}, device_scale_factor=1.5)

            page.goto(URL)
            page.screenshot(path=OUT / "01-empty.png")

            # 1. загружаем три скриншота через настоящий input
            page.set_input_files("input[type=file]", [str(f) for f in sorted((ROOT / "samples").glob("*.png"))])
            page.click("text=Распознать книги")
            page.wait_for_selector(".item")
            page.add_style_tag(content=".bar{position:static}")
            page.screenshot(path=OUT / "02-review.png", full_page=True)

            # 2. сохраняем в библиотеку
            page.click("text=Сохранить в библиотеку")
            page.wait_for_selector(".group")
            page.screenshot(path=OUT / "03-by-authors.png")

            # 3. жанры
            page.click("text=По жанрам")
            page.wait_for_selector(".group")
            page.screenshot(path=OUT / "04-by-genres.png")
            browser.close()
        print("screenshots saved to", OUT)
    finally:
        server.terminate()
        shutil.rmtree(data, ignore_errors=True)


if __name__ == "__main__":
    main()
