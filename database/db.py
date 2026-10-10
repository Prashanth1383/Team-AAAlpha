"""SQLite helpers and database lifecycle."""

from __future__ import annotations

import hashlib
import secrets
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Optional

from flask import Flask, current_app, g

DEMO_STUDENT_NAME = "Demo Student"


def utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def get_db() -> sqlite3.Connection:
    if "db" not in g:
        path = Path(current_app.config["DATABASE_PATH"])
        path.parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(path)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        g.db = conn
    return g.db


def close_db(_e: Optional[BaseException] = None) -> None:
    conn = g.pop("db", None)
    if conn is not None:
        conn.close()


def query_all(sql: str, params: Iterable[Any] = ()) -> list[sqlite3.Row]:
    return get_db().execute(sql, tuple(params)).fetchall()


def query_one(sql: str, params: Iterable[Any] = ()) -> Optional[sqlite3.Row]:
    return get_db().execute(sql, tuple(params)).fetchone()


def execute(sql: str, params: Iterable[Any] = ()) -> sqlite3.Cursor:
    return get_db().execute(sql, tuple(params))


def init_schema(app: Flask) -> None:
    schema_path = Path(app.root_path) / "database" / "schema.sql"
    sql = schema_path.read_text(encoding="utf-8")
    with app.app_context():
        db = get_db()
        db.executescript(sql)
        db.commit()


def get_or_create_demo_student() -> sqlite3.Row:
    row = query_one("SELECT * FROM students ORDER BY id ASC LIMIT 1")
    if row:
        return row
    db = get_db()
    cursor = db.execute(
        "INSERT INTO students (display_name, created_at) VALUES (?, ?)",
        (DEMO_STUDENT_NAME, utc_now()),
    )
    db.commit()
    student = query_one("SELECT * FROM students WHERE id = ?", (cursor.lastrowid,))
    assert student is not None
    return student


def hash_password(password: str) -> str:
    salt = secrets.token_hex(8)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt.encode("utf-8"), 120000)
    return f"{salt}:{digest.hex()}"


def verify_password(password: str, password_hash: str) -> bool:
    try:
        salt, expected = password_hash.split(":", 1)
    except ValueError:
        return False
    candidate = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt.encode("utf-8"), 120000)
    return secrets.compare_digest(candidate.hex(), expected)


def get_user_by_username(username: str) -> Optional[sqlite3.Row]:
    normalized = username.strip().lower()
    if not normalized:
        return None
    return query_one("SELECT * FROM app_users WHERE LOWER(username) = ?", (normalized,))


def ensure_student_for_user(user_id: int, display_name: str) -> int:
    user = query_one("SELECT * FROM app_users WHERE id = ?", (user_id,))
    if user is None:
        raise ValueError("User not found.")
    if user["student_id"]:
        return int(user["student_id"])

    existing = query_one(
        "SELECT id FROM students WHERE display_name = ? ORDER BY id ASC LIMIT 1",
        (display_name,),
    )
    if existing is not None:
        student_id = int(existing["id"])
    else:
        db = get_db()
        cursor = db.execute(
            "INSERT INTO students (display_name, created_at) VALUES (?, ?)",
            (display_name, utc_now()),
        )
        db.commit()
        student_id = int(cursor.lastrowid)

    db = get_db()
    db.execute("UPDATE app_users SET student_id = ? WHERE id = ?", (student_id, user_id))
    db.commit()
    return student_id


def create_app_user(username: str, password: str) -> sqlite3.Row:
    normalized = username.strip()
    if len(normalized) < 3:
        raise ValueError("Username must be at least 3 characters.")
    if len(password) < 6:
        raise ValueError("Password must be at least 6 characters.")
    if get_user_by_username(normalized) is not None:
        raise ValueError("That username is already taken.")

    db = get_db()
    password_hash = hash_password(password)
    cursor = db.execute(
        "INSERT INTO app_users (username, password_hash, created_at) VALUES (?, ?, ?)",
        (normalized, password_hash, utc_now()),
    )
    db.commit()
    user = query_one("SELECT * FROM app_users WHERE id = ?", (cursor.lastrowid,))
    assert user is not None
    return user


def authenticate_user(username: str, password: str) -> Optional[sqlite3.Row]:
    user = get_user_by_username(username)
    if user is None:
        return None
    if not verify_password(password, user["password_hash"]):
        return None
    return user


def init_app(app: Flask) -> None:
    app.teardown_appcontext(close_db)

    @app.cli.command("init-db")
    def init_db_command() -> None:
        """Create tables and load starter quiz questions and resources."""
        from database.seed import seed_database

        init_schema(app)
        with app.app_context():
            seed_database()
        print("Database initialized and seeded.")
