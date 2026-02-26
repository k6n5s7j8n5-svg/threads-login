import os
import sqlite3
from typing import Optional, Tuple

DB_PATH = os.getenv("DB_PATH", "/app/data/app.db")

def _conn():
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    return sqlite3.connect(DB_PATH)

def init_db():
    with _conn() as con:
        cur = con.cursor()
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS status (
              id INTEGER PRIMARY KEY CHECK (id = 1),
              people INTEGER NOT NULL DEFAULT 0,
              oysters INTEGER NOT NULL DEFAULT 0,
              updated_at TEXT NOT NULL DEFAULT (datetime('now'))
            )
            """
        )
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS draft (
              id INTEGER PRIMARY KEY CHECK (id = 1),
              text TEXT,
              approved INTEGER NOT NULL DEFAULT 0,
              updated_at TEXT NOT NULL DEFAULT (datetime('now'))
            )
            """
        )
        cur.execute("INSERT OR IGNORE INTO status (id, people, oysters) VALUES (1, 0, 0)")
        cur.execute("INSERT OR IGNORE INTO draft (id, text, approved) VALUES (1, NULL, 0)")
        con.commit()

def get_status() -> Tuple[int, int, str]:
    with _conn() as con:
        cur = con.cursor()
        row = cur.execute("SELECT people, oysters, updated_at FROM status WHERE id=1").fetchone()
        return int(row[0]), int(row[1]), str(row[2])

def set_status(people: Optional[int] = None, oysters: Optional[int] = None):
    p, o, _ = get_status()
    if people is None:
        people = p
    if oysters is None:
        oysters = o
    with _conn() as con:
        cur = con.cursor()
        cur.execute(
            "UPDATE status SET people=?, oysters=?, updated_at=datetime('now') WHERE id=1",
            (int(people), int(oysters)),
        )
        con.commit()

def get_draft() -> Tuple[Optional[str], bool, str]:
    with _conn() as con:
        cur = con.cursor()
        row = cur.execute("SELECT text, approved, updated_at FROM draft WHERE id=1").fetchone()
        text = row[0]
        approved = bool(row[1])
        return text, approved, str(row[2])

def set_draft(text: Optional[str], approved: bool):
    with _conn() as con:
        cur = con.cursor()
        cur.execute(
            "UPDATE draft SET text=?, approved=?, updated_at=datetime('now') WHERE id=1",
            (text, 1 if approved else 0),
        )
        con.commit()
