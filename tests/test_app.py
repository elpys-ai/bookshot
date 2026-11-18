import io
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pytest

from app import create_app


@pytest.fixture()
def client(tmp_path):
    app = create_app(str(tmp_path))
    app.config["TESTING"] = True
    return app.test_client()


def test_library_empty(client):
    r = client.get("/")
    assert r.status_code == 200 and "Пока пусто" in r.get_data(as_text=True)


def test_paste_review_save_flow(client):
    r = client.post("/upload", data={"pasted": "«1984» — Джордж Оруэлл\nАтомные привычки, Джеймс Клир"})
    assert r.status_code == 302 and "/review" in r.headers["Location"]
    page = client.get(r.headers["Location"]).get_data(as_text=True)
    assert "1984" in page and "Джордж Оруэлл" in page

    r = client.post("/review/save", data={
        "count": "2",
        "keep_0": "on", "title_0": "1984", "author_0": "Оруэлл", "genre_0": "Антиутопия", "shot_0": "1",
        "keep_1": "on", "title_1": "Атомные привычки", "author_1": "Клир", "genre_1": "Саморазвитие", "shot_1": "1",
    })
    assert r.status_code == 302
    html = client.get("/?view=authors").get_data(as_text=True)
    assert "Джордж Оруэлл" in html and "Джеймс Клир" in html  # «Оруэлл» → каноничное имя
    assert "Саморазвитие" in client.get("/?view=genres").get_data(as_text=True)


def test_duplicates_not_added_twice(client):
    for _ in range(2):
        client.post("/books", data={"title": "Дюна", "author": "Фрэнк Герберт"})
    html = client.get("/?view=all").get_data(as_text=True)
    assert html.count("<h4>Дюна</h4>") == 1


def test_toggle_delete_and_export(client):
    client.post("/books", data={"title": "Идиот", "author": "Достоевский"})
    assert "✓ прочитано" not in client.get("/?view=all").get_data(as_text=True)
    client.post("/books/1/toggle")
    assert "✓ прочитано" in client.get("/?view=all").get_data(as_text=True)
    csv_text = client.get("/export.csv").get_data(as_text=True)
    assert "Идиот" in csv_text and "Фёдор Достоевский" in csv_text
    client.post("/books/1/delete")
    assert "Идиот" not in client.get("/?view=all").get_data(as_text=True)


def test_rejects_bad_extension(client):
    r = client.post("/upload", data={"screenshots": (io.BytesIO(b"x"), "evil.exe")},
                    content_type="multipart/form-data", follow_redirects=True)
    assert "не поддерживается" in r.get_data(as_text=True)
