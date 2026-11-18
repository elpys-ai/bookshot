"""BookShot — превращает скриншоты с рекомендациями книг в библиотеку по авторам и жанрам."""
from __future__ import annotations

import csv
import io
import os
import sqlite3
import uuid
from collections import defaultdict
from pathlib import Path

from flask import (Flask, Response, abort, flash, g, redirect, render_template,
                   request, send_from_directory, url_for)
from werkzeug.utils import secure_filename

from bookparser import parse_books
from genres import GENRES, UNKNOWN_AUTHOR, guess, lookup_author
from ocr import extract_text, ocr_available

ALLOWED = {".png", ".jpg", ".jpeg", ".webp", ".gif"}

SCHEMA = """
CREATE TABLE IF NOT EXISTS screenshots (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    filename TEXT NOT NULL,
    ocr_text TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE IF NOT EXISTS books (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    title TEXT NOT NULL,
    author TEXT NOT NULL,
    genre TEXT NOT NULL DEFAULT 'Другое',
    is_read INTEGER NOT NULL DEFAULT 0,
    screenshot_id INTEGER REFERENCES screenshots(id) ON DELETE SET NULL,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE (title COLLATE NOCASE, author COLLATE NOCASE)
);
"""


def create_app(data_dir: str | None = None) -> Flask:
    app = Flask(__name__)
    data = Path(data_dir or os.environ.get("BOOKSHOT_DATA", "data")).resolve()
    (data / "uploads").mkdir(parents=True, exist_ok=True)
    app.config.update(
        DATA_DIR=data,
        DB_PATH=data / "bookshot.db",
        UPLOAD_DIR=data / "uploads",
        MAX_CONTENT_LENGTH=25 * 1024 * 1024,
        SECRET_KEY=os.environ.get("SECRET_KEY", "dev-only-change-me"),
    )

    def db() -> sqlite3.Connection:
        if "db" not in g:
            g.db = sqlite3.connect(app.config["DB_PATH"])
            g.db.row_factory = sqlite3.Row
            g.db.execute("PRAGMA foreign_keys = ON")
        return g.db

    @app.teardown_appcontext
    def close_db(_exc):
        conn = g.pop("db", None)
        if conn is not None:
            conn.close()

    with sqlite3.connect(app.config["DB_PATH"]) as conn:
        conn.executescript(SCHEMA)

    # ---------- библиотека ----------
    @app.get("/")
    def library():
        view = request.args.get("view", "authors")
        if view not in {"all", "authors", "genres"}:
            view = "authors"
        q = request.args.get("q", "").strip()
        genre = request.args.get("genre", "").strip()
        author = request.args.get("author", "").strip()

        sql, args = "SELECT * FROM books WHERE 1=1", []
        if q:
            sql += " AND (title LIKE ? OR author LIKE ?)"
            args += [f"%{q}%", f"%{q}%"]
        if genre:
            sql += " AND genre = ?"
            args.append(genre)
        if author:
            sql += " AND author = ?"
            args.append(author)
        books = db().execute(sql + " ORDER BY title COLLATE NOCASE", args).fetchall()

        groups: dict[str, list] = defaultdict(list)
        if view == "all":
            groups[""] = list(books)
        else:
            for b in books:
                groups[b["author"] if view == "authors" else b["genre"]].append(b)
        ordered = sorted(groups.items(), key=lambda kv: (kv[0] == UNKNOWN_AUTHOR, kv[0].lower()))

        stats = db().execute(
            "SELECT COUNT(*) n, COUNT(DISTINCT author) a, COUNT(DISTINCT genre) g, "
            "SUM(is_read) r FROM books"
        ).fetchone()
        shots = db().execute("SELECT COUNT(*) FROM screenshots").fetchone()[0]
        return render_template(
            "library.html", groups=ordered, view=view, q=q, genre=genre, author=author,
            stats=stats, shots=shots, genres=GENRES, total=len(books),
        )

    @app.post("/books")
    def add_book():
        title = request.form.get("title", "").strip()
        author = request.form.get("author", "").strip()
        if not title:
            flash("Укажи название книги")
            return redirect(url_for("library"))
        hit = lookup_author(author) if author else None
        author = hit[0] if hit else (author or UNKNOWN_AUTHOR)
        genre = request.form.get("genre") or guess(author)
        _insert_book(db(), title, author, genre, None)
        db().commit()
        return redirect(url_for("library", view="all"))

    @app.post("/books/<int:book_id>/toggle")
    def toggle_read(book_id: int):
        db().execute("UPDATE books SET is_read = 1 - is_read WHERE id = ?", (book_id,))
        db().commit()
        return redirect(request.referrer or url_for("library"))

    @app.post("/books/<int:book_id>/delete")
    def delete_book(book_id: int):
        db().execute("DELETE FROM books WHERE id = ?", (book_id,))
        db().commit()
        return redirect(request.referrer or url_for("library"))

    # ---------- загрузка скриншотов ----------
    @app.post("/upload")
    def upload():
        ids = []
        for f in request.files.getlist("screenshots"):
            if not f or not f.filename:
                continue
            ext = Path(secure_filename(f.filename) or "x.png").suffix.lower()
            if ext not in ALLOWED:
                flash(f"Формат {ext or '?'} не поддерживается: {f.filename}")
                continue
            name = f"{uuid.uuid4().hex[:12]}{ext}"
            path = app.config["UPLOAD_DIR"] / name
            f.save(path)
            ids.append(_new_screenshot(db(), name, extract_text(str(path))))

        pasted = request.form.get("pasted", "").strip()
        if pasted:
            ids.append(_new_screenshot(db(), "", pasted))

        if not ids:
            flash("Выбери хотя бы один скриншот или вставь текст")
            return redirect(url_for("library"))
        db().commit()
        return redirect(url_for("review", ids=",".join(map(str, ids))))

    @app.get("/review")
    def review():
        ids = [int(i) for i in request.args.get("ids", "").split(",") if i.isdigit()]
        if not ids:
            return redirect(url_for("library"))
        marks = ",".join("?" * len(ids))
        shots = db().execute(f"SELECT * FROM screenshots WHERE id IN ({marks})", ids).fetchall()
        sections = [{"shot": s, "items": parse_books(s["ocr_text"])} for s in shots]
        return render_template("review.html", sections=sections, genres=GENRES,
                               ocr_ok=ocr_available())

    @app.post("/review/save")
    def review_save():
        added = 0
        for i in range(int(request.form.get("count", 0))):
            if not request.form.get(f"keep_{i}"):
                continue
            title = request.form.get(f"title_{i}", "").strip()
            author = request.form.get(f"author_{i}", "").strip()
            if not title:
                continue
            hit = lookup_author(author) if author else None
            author = hit[0] if hit else (author or UNKNOWN_AUTHOR)
            shot = request.form.get(f"shot_{i}", type=int)
            added += _insert_book(db(), title, author,
                                  request.form.get(f"genre_{i}") or guess(author), shot)
        db().commit()
        flash(f"Добавлено книг: {added}")
        return redirect(url_for("library"))

    @app.get("/uploads/<path:name>")
    def uploaded(name):
        return send_from_directory(app.config["UPLOAD_DIR"], name)

    @app.get("/export.csv")
    def export_csv():
        rows = db().execute(
            "SELECT title, author, genre, is_read FROM books ORDER BY author, title").fetchall()
        buf = io.StringIO()
        w = csv.writer(buf)
        w.writerow(["title", "author", "genre", "is_read"])
        w.writerows([tuple(r) for r in rows])
        return Response("﻿" + buf.getvalue(), mimetype="text/csv",
                        headers={"Content-Disposition": "attachment; filename=bookshot.csv"})

    return app


def _new_screenshot(conn, filename: str, text: str) -> int:
    cur = conn.execute("INSERT INTO screenshots (filename, ocr_text) VALUES (?, ?)", (filename, text))
    return cur.lastrowid


def _insert_book(conn, title, author, genre, shot_id) -> int:
    if genre not in GENRES:
        genre = "Другое"
    cur = conn.execute(
        "INSERT OR IGNORE INTO books (title, author, genre, screenshot_id) VALUES (?, ?, ?, ?)",
        (title, author, genre, shot_id))
    return cur.rowcount


app = create_app()

if __name__ == "__main__":
    app.run(host="127.0.0.1", port=int(os.environ.get("PORT", 5000)), debug=bool(os.environ.get("DEBUG")))
