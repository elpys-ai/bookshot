# Shelfie

Flask + SQLite + Tesseract. Превращает скриншоты с рекомендациями книг в библиотеку по авторам и жанрам.

## Команды
- Запуск: `python app.py` → http://127.0.0.1:5000
- Тесты: `python -m pytest -q`
- Примеры скриншотов: `python scripts/make_samples.py`
- Скриншоты для README: `python scripts/take_screenshots.py`

Общие инструкции для всех агентов: см. AGENTS.md.

## Правила
- Логика разбора строк живёт только в `bookparser.py`; каждое исправление парсера сопровождается тестом в `tests/test_parser.py`.
- Известные авторы и жанры — в `genres.py`.
- Данные пользователя (`data/`) не коммитим.
- Тексты интерфейса — на русском.
