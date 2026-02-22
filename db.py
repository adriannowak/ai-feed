import sqlite3
import json
from pathlib import Path
from datetime import datetime

DB_PATH = Path("feed.db")


def get_conn():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    conn = get_conn()
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS items (
            id          TEXT PRIMARY KEY,
            url         TEXT UNIQUE NOT NULL,
            title       TEXT,
            source      TEXT,
            published   TEXT,
            text        TEXT,
            summary     TEXT,
            embedding   TEXT,
            llm_score   REAL,
            llm_topics  TEXT,
            llm_reason  TEXT,
            notified    INTEGER DEFAULT 0,
            created_at  TEXT DEFAULT (datetime('now'))
        );

        CREATE TABLE IF NOT EXISTS feedback (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            item_id     TEXT NOT NULL,
            signal      INTEGER NOT NULL,
            created_at  TEXT DEFAULT (datetime('now')),
            FOREIGN KEY (item_id) REFERENCES items(id)
        );

        CREATE TABLE IF NOT EXISTS daily_packs (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            date        TEXT UNIQUE NOT NULL,
            item_ids    TEXT,
            brief_md    TEXT,
            nb_id       TEXT,
            created_at  TEXT DEFAULT (datetime('now'))
        );
    """)
    conn.commit()
    conn.close()


def item_exists(url: str) -> bool:
    conn = get_conn()
    row = conn.execute("SELECT 1 FROM items WHERE url=?", (url,)).fetchone()
    conn.close()
    return row is not None


def insert_item(item: dict):
    conn = get_conn()
    conn.execute("""
        INSERT OR IGNORE INTO items
            (id, url, title, source, published, text, summary, embedding)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        item["id"], item["url"], item["title"], item["source"],
        item["published"], item["text"], item.get("summary"),
        json.dumps(item.get("embedding")) if item.get("embedding") else None,
    ))
    conn.commit()
    conn.close()


def update_item_score(item_id: str, score: float, topics: list, reason: str):
    conn = get_conn()
    conn.execute("""
        UPDATE items SET llm_score=?, llm_topics=?, llm_reason=?
        WHERE id=?
    """, (score, json.dumps(topics), reason, item_id))
    conn.commit()
    conn.close()


def mark_notified(item_id: str):
    conn = get_conn()
    conn.execute("UPDATE items SET notified=1 WHERE id=?", (item_id,))
    conn.commit()
    conn.close()


def add_feedback(item_id: str, signal: int):
    conn = get_conn()
    conn.execute(
        "INSERT INTO feedback (item_id, signal) VALUES (?, ?)",
        (item_id, signal)
    )
    conn.commit()
    conn.close()


def get_liked_items(limit: int = 50) -> list[dict]:
    conn = get_conn()
    rows = conn.execute("""
        SELECT i.id, i.title, i.summary, i.embedding, i.llm_topics
        FROM items i
        JOIN feedback f ON f.item_id = i.id
        WHERE f.signal = 1
        ORDER BY f.created_at DESC
        LIMIT ?
    """, (limit,)).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_disliked_items(limit: int = 50) -> list[dict]:
    conn = get_conn()
    rows = conn.execute("""
        SELECT i.id, i.title, i.summary, i.embedding, i.llm_topics
        FROM items i
        JOIN feedback f ON f.item_id = i.id
        WHERE f.signal = -1
        ORDER BY f.created_at DESC
        LIMIT ?
    """, (limit,)).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_today_top_items(min_score: float, max_items: int) -> list[dict]:
    conn = get_conn()
    rows = conn.execute("""
        SELECT * FROM items
        WHERE date(created_at) = date('now')
          AND llm_score >= ?
        ORDER BY llm_score DESC
        LIMIT ?
    """, (min_score, max_items)).fetchall()
    conn.close()
    return [dict(r) for r in rows]
