import sqlite3
import json
import numpy as np
from pathlib import Path

DB_PATH = Path("feed.db")


def get_conn():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    conn = get_conn()
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS users (
            user_id     INTEGER PRIMARY KEY,
            username    TEXT,
            created_at  TEXT DEFAULT (datetime('now'))
        );

        CREATE TABLE IF NOT EXISTS user_feeds (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id     INTEGER NOT NULL,
            url         TEXT NOT NULL,
            added_at    TEXT DEFAULT (datetime('now')),
            UNIQUE(user_id, url),
            FOREIGN KEY (user_id) REFERENCES users(user_id)
        );

        CREATE TABLE IF NOT EXISTS items (
            id          TEXT PRIMARY KEY,
            url         TEXT UNIQUE NOT NULL,
            title       TEXT,
            source      TEXT,
            published   TEXT,
            text        TEXT,
            summary     TEXT,
            embedding   TEXT,
            created_at  TEXT DEFAULT (datetime('now'))
        );

        CREATE TABLE IF NOT EXISTS user_item_scores (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id     INTEGER NOT NULL,
            item_id     TEXT NOT NULL,
            llm_score   REAL,
            llm_topics  TEXT,
            llm_reason  TEXT,
            notified    INTEGER DEFAULT 0,
            UNIQUE(user_id, item_id),
            FOREIGN KEY (user_id) REFERENCES users(user_id),
            FOREIGN KEY (item_id) REFERENCES items(id)
        );

        CREATE TABLE IF NOT EXISTS feedback (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id     INTEGER NOT NULL,
            item_id     TEXT NOT NULL,
            signal      INTEGER NOT NULL,
            created_at  TEXT DEFAULT (datetime('now')),
            FOREIGN KEY (user_id) REFERENCES users(user_id),
            FOREIGN KEY (item_id) REFERENCES items(id)
        );

        CREATE TABLE IF NOT EXISTS tracked_articles (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id     INTEGER NOT NULL,
            url         TEXT NOT NULL,
            embedding   TEXT,
            added_at    TEXT DEFAULT (datetime('now')),
            FOREIGN KEY (user_id) REFERENCES users(user_id)
        );

        CREATE TABLE IF NOT EXISTS daily_packs (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id     INTEGER NOT NULL,
            date        TEXT NOT NULL,
            item_ids    TEXT,
            brief_md    TEXT,
            created_at  TEXT DEFAULT (datetime('now')),
            UNIQUE(user_id, date)
        );
    """)
    conn.commit()
    conn.close()


# --- User management ---

def register_user(user_id: int, username: str | None = None):
    conn = get_conn()
    conn.execute(
        "INSERT OR IGNORE INTO users (user_id, username) VALUES (?, ?)",
        (user_id, username)
    )
    conn.commit()
    conn.close()


def get_all_users() -> list[dict]:
    conn = get_conn()
    rows = conn.execute("SELECT * FROM users").fetchall()
    conn.close()
    return [dict(r) for r in rows]


# --- Feed subscriptions ---

def add_user_feed(user_id: int, url: str):
    conn = get_conn()
    conn.execute(
        "INSERT OR IGNORE INTO user_feeds (user_id, url) VALUES (?, ?)",
        (user_id, url)
    )
    conn.commit()
    conn.close()


def get_user_feeds(user_id: int) -> list[str]:
    conn = get_conn()
    rows = conn.execute(
        "SELECT url FROM user_feeds WHERE user_id=?", (user_id,)
    ).fetchall()
    conn.close()
    return [r["url"] for r in rows]


# --- Items (shared, deduped by URL) ---

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


# --- Per-user scoring ---

def save_user_score(user_id: int, item_id: str, score: float, topics: list, reason: str):
    conn = get_conn()
    conn.execute("""
        INSERT OR REPLACE INTO user_item_scores
            (user_id, item_id, llm_score, llm_topics, llm_reason)
        VALUES (?, ?, ?, ?, ?)
    """, (user_id, item_id, score, json.dumps(topics), reason))
    conn.commit()
    conn.close()


def get_unnotified_items(user_id: int) -> list[dict]:
    conn = get_conn()
    rows = conn.execute("""
        SELECT i.*, s.llm_score, s.llm_topics, s.llm_reason
        FROM items i
        JOIN user_item_scores s ON s.item_id = i.id
        WHERE s.user_id = ? AND s.notified = 0
        ORDER BY s.llm_score DESC
    """, (user_id,)).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def mark_notified(user_id: int, item_id: str):
    conn = get_conn()
    conn.execute(
        "UPDATE user_item_scores SET notified=1 WHERE user_id=? AND item_id=?",
        (user_id, item_id)
    )
    conn.commit()
    conn.close()


# --- Feedback ---

def save_feedback(user_id: int, item_id: str, signal: int):
    conn = get_conn()
    conn.execute(
        "INSERT INTO feedback (user_id, item_id, signal) VALUES (?, ?, ?)",
        (user_id, item_id, signal)
    )
    conn.commit()
    conn.close()


def get_liked_items(user_id: int, limit: int = 50) -> list[dict]:
    conn = get_conn()
    rows = conn.execute("""
        SELECT i.id, i.title, i.summary, i.embedding, s.llm_topics
        FROM items i
        JOIN feedback f ON f.item_id = i.id
        LEFT JOIN user_item_scores s ON s.item_id = i.id AND s.user_id = f.user_id
        WHERE f.user_id = ? AND f.signal = 1
        ORDER BY f.created_at DESC
        LIMIT ?
    """, (user_id, limit)).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_disliked_items(user_id: int, limit: int = 50) -> list[dict]:
    conn = get_conn()
    rows = conn.execute("""
        SELECT i.id, i.title, i.summary, i.embedding, s.llm_topics
        FROM items i
        JOIN feedback f ON f.item_id = i.id
        LEFT JOIN user_item_scores s ON s.item_id = i.id AND s.user_id = f.user_id
        WHERE f.user_id = ? AND f.signal = -1
        ORDER BY f.created_at DESC
        LIMIT ?
    """, (user_id, limit)).fetchall()
    conn.close()
    return [dict(r) for r in rows]


# --- Tracked articles ---

def add_tracked_article(user_id: int, url: str, embedding: list | None = None):
    conn = get_conn()
    conn.execute(
        "INSERT INTO tracked_articles (user_id, url, embedding) VALUES (?, ?, ?)",
        (user_id, url, json.dumps(embedding) if embedding else None)
    )
    conn.commit()
    conn.close()


def get_tracked_embeddings(user_id: int) -> list[np.ndarray]:
    conn = get_conn()
    rows = conn.execute(
        "SELECT embedding FROM tracked_articles WHERE user_id=? AND embedding IS NOT NULL",
        (user_id,)
    ).fetchall()
    conn.close()
    return [np.array(json.loads(r["embedding"])) for r in rows]


# --- Daily packs ---

def get_today_top_items(user_id: int, min_score: float, max_items: int) -> list[dict]:
    conn = get_conn()
    rows = conn.execute("""
        SELECT i.*, s.llm_score, s.llm_topics, s.llm_reason
        FROM items i
        JOIN user_item_scores s ON s.item_id = i.id
        WHERE s.user_id = ?
          AND date(i.created_at) = date('now')
          AND s.llm_score >= ?
        ORDER BY s.llm_score DESC
        LIMIT ?
    """, (user_id, min_score, max_items)).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def save_daily_pack(user_id: int, date: str, item_ids: list, brief_md: str):
    conn = get_conn()
    conn.execute("""
        INSERT OR REPLACE INTO daily_packs (user_id, date, item_ids, brief_md)
        VALUES (?, ?, ?, ?)
    """, (user_id, date, json.dumps(item_ids), brief_md))
    conn.commit()
    conn.close()
