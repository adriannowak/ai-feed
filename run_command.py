"""
Serverless bot command handler — called by the bot_command GitHub Actions workflow.

Reads USER_ID, CHAT_ID, COMMAND, and ARGS from env vars, performs the
requested action (register, add feed, track article, list feeds), and
replies to the user via the Telegram Bot API.

Environment variables:
  TELEGRAM_BOT_TOKEN  — bot token
  USER_ID             — Telegram user_id (integer)
  CHAT_ID             — Telegram chat_id to reply to (integer)
  USERNAME            — Telegram username (may be empty)
  COMMAND             — one of: start, add, track, feeds
  ARGS                — optional command argument (e.g. the RSS URL for /add)
"""
import os
import requests

from dotenv import load_dotenv

from config import FEEDS
from db import (
    add_tracked_article,
    add_user_feed,
    get_user_feeds,
    init_db,
    register_user,
)
from embeddings import embed_text


def _reply(bot_token: str, chat_id: int, text: str) -> None:
    """Send a plain-text message to the user."""
    resp = requests.post(
        f"https://api.telegram.org/bot{bot_token}/sendMessage",
        json={"chat_id": chat_id, "text": text},
    )
    if not resp.ok:
        print(f"[run_command] Telegram reply failed: {resp.text}")


def handle_start(bot_token: str, user_id: int, chat_id: int, username: str) -> None:
    register_user(user_id, username or None)
    for feed_url in FEEDS:
        add_user_feed(user_id, feed_url)
    _reply(
        bot_token,
        chat_id,
        "Welcome! 🎉\n\n"
        "Use /add <rss_url> to subscribe to additional feeds.\n"
        "Use /track <article_url> to seed your taste profile with a specific article.\n\n"
        f"You are now subscribed to {len(FEEDS)} default feed(s).",
    )


def handle_add(bot_token: str, user_id: int, chat_id: int, username: str, url: str) -> None:
    if not url:
        _reply(bot_token, chat_id, "Usage: /add <rss_url>")
        return

    import feedparser

    register_user(user_id, username or None)
    feed = feedparser.parse(url)
    if feed.bozo and not feed.entries:
        _reply(
            bot_token,
            chat_id,
            f"⚠️ Could not parse a valid RSS feed at:\n{url}\n\nPlease check the URL and try again.",
        )
        return

    add_user_feed(user_id, url)
    feed_title = feed.feed.get("title", url)
    _reply(bot_token, chat_id, f"✅ Subscribed to {feed_title}")


def handle_track(bot_token: str, user_id: int, chat_id: int, username: str, url: str) -> None:
    if not url:
        _reply(bot_token, chat_id, "Usage: /track <article_url>")
        return

    register_user(user_id, username or None)
    _reply(bot_token, chat_id, "⏳ Fetching and embedding article…")

    try:
        import trafilatura

        downloaded = trafilatura.fetch_url(url)
        text = ""
        if downloaded:
            text = trafilatura.extract(
                downloaded,
                include_comments=False,
                include_tables=False,
                no_fallback=False,
            ) or ""

        embedding = embed_text(text) if text else None
        add_tracked_article(user_id, url, embedding)
        _reply(bot_token, chat_id, f"✅ Tracking article for your taste profile:\n{url}")
    except Exception as exc:
        print(f"[run_command] error tracking {url}: {exc}")
        _reply(bot_token, chat_id, f"⚠️ Could not track article: {exc}")


def handle_feeds(bot_token: str, user_id: int, chat_id: int, username: str) -> None:
    register_user(user_id, username or None)
    feeds = get_user_feeds(user_id)
    if not feeds:
        _reply(bot_token, chat_id, "You have no feed subscriptions yet. Use /add <rss_url>.")
        return
    lines = "\n".join(f"• {f}" for f in feeds)
    _reply(bot_token, chat_id, f"Your subscriptions ({len(feeds)}):\n{lines}")


def main() -> None:
    init_db()

    bot_token = os.environ["TELEGRAM_BOT_TOKEN"]
    user_id = int(os.environ["USER_ID"])
    chat_id = int(os.environ["CHAT_ID"])
    username = os.environ.get("USERNAME", "")
    command = os.environ.get("COMMAND", "").lstrip("/").lower()
    args = os.environ.get("ARGS", "").strip()

    print(f"[run_command] user={user_id} command={command} args={args!r}")

    if command == "start":
        handle_start(bot_token, user_id, chat_id, username)
    elif command == "add":
        handle_add(bot_token, user_id, chat_id, username, args)
    elif command == "track":
        handle_track(bot_token, user_id, chat_id, username, args)
    elif command == "feeds":
        handle_feeds(bot_token, user_id, chat_id, username)
    else:
        _reply(
            bot_token,
            chat_id,
            "Unknown command. Available commands:\n"
            "/start — register & subscribe to default feeds\n"
            "/add <rss_url> — subscribe to an RSS feed\n"
            "/track <article_url> — seed your taste profile\n"
            "/feeds — list your subscriptions",
        )


if __name__ == "__main__":
    load_dotenv()
    main()
