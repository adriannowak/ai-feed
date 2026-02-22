"""Telegram bot for the AI feed — handles user registration, feed subscriptions,
article tracking, and 👍/👎 feedback callbacks.

Run with:
    python bot.py

Requires TELEGRAM_BOT_TOKEN in the environment (or a .env file).
"""
import logging
import os

import feedparser
from dotenv import load_dotenv
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import (
    Application,
    CallbackQueryHandler,
    CommandHandler,
    ContextTypes,
)

from config import FEEDS, ALLOWED_USER_IDS
from db import (
    add_tracked_article,
    add_user_feed,
    get_user_feeds,
    init_db,
    register_user,
    save_feedback,
)
from embeddings import embed_text

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)


def _is_allowed(user_id: int) -> bool:
    """Return True if the user is on the invite-only allowlist."""
    return user_id in ALLOWED_USER_IDS


async def _deny(update: Update) -> None:
    """Send a consistent rejection message."""
    await update.message.reply_text(
        "⛔ Sorry, this bot is invite-only. Contact the owner to request access."
    )


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """/start — register user and subscribe to default feeds."""
    user = update.effective_user
    if not _is_allowed(user.id):
        await _deny(update)
        return
    register_user(user.id, user.username)

    for feed_url in FEEDS:
        add_user_feed(user.id, feed_url)

    await update.message.reply_text(
        "Welcome! 🎉\n\n"
        "Use /add <rss_url> to subscribe to additional feeds.\n"
        "Use /feeds to see your current subscriptions.\n"
        "Use /track <article_url> to seed your taste profile with a specific article.\n\n"
        f"You are now subscribed to {len(FEEDS)} default feed(s)."
    )


async def add_feed(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """/add <rss_url> — subscribe the user to an RSS feed."""
    user = update.effective_user
    if not _is_allowed(user.id):
        await _deny(update)
        return
    register_user(user.id, user.username)

    if not context.args:
        await update.message.reply_text("Usage: /add <rss_url>")
        return

    url = context.args[0].strip()

    await update.message.reply_text("⏳ Validating feed…")

    # Validate by parsing the feed
    feed = feedparser.parse(url)
    if feed.bozo and not feed.entries:
        await update.message.reply_text(
            f"⚠️ Could not parse a valid RSS feed at:\n{url}\n\nPlease check the URL and try again."
        )
        return

    add_user_feed(user.id, url)
    feed_title = feed.feed.get("title", url)
    await update.message.reply_text(f"✅ Subscribed to *{feed_title}*", parse_mode="Markdown")


async def track_article(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """/track <article_url> — seed preference profile with a specific article."""
    user = update.effective_user
    if not _is_allowed(user.id):
        await _deny(update)
        return
    register_user(user.id, user.username)

    if not context.args:
        await update.message.reply_text("Usage: /track <article_url>")
        return

    url = context.args[0].strip()

    await update.message.reply_text(f"⏳ Fetching and embedding article…")

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
        add_tracked_article(user.id, url, embedding)

        await update.message.reply_text(
            f"✅ Tracking article for your taste profile:\n{url}"
        )
    except Exception as exc:
        logger.exception("Error tracking article %s", url)
        await update.message.reply_text(f"⚠️ Could not track article: {exc}")


async def list_feeds(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """/feeds — list the user's current feed subscriptions."""
    user = update.effective_user
    if not _is_allowed(user.id):
        await _deny(update)
        return
    register_user(user.id, user.username)

    feeds = get_user_feeds(user.id)
    if not feeds:
        await update.message.reply_text("You have no feed subscriptions yet. Use /add <rss_url>.")
        return

    lines = "\n".join(f"• {f}" for f in feeds)
    await update.message.reply_text(f"Your subscriptions ({len(feeds)}):\n{lines}")


async def handle_feedback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle 👍 / 👎 inline keyboard callbacks."""
    query = update.callback_query
    user_id = query.from_user.id

    if not _is_allowed(user_id):
        await query.answer("⛔ Access denied.")
        return

    data = query.data  # "like:<item_id>" or "dislike:<item_id>"

    parts = data.split(":", 1)
    if len(parts) != 2:
        await query.answer()
        return

    action, item_id = parts
    signal = 1 if action == "like" else -1

    try:
        save_feedback(user_id, item_id, signal)
        ack = "👍 Liked!" if signal == 1 else "👎 Disliked!"
        await query.answer(ack)
        # Update the message to remove the keyboard so the user can't vote twice
        await query.edit_message_reply_markup(reply_markup=InlineKeyboardMarkup([]))
    except Exception as exc:
        logger.exception("Error saving feedback for user=%s item=%s", user_id, item_id)
        await query.answer("⚠️ Could not save feedback.")


def main() -> None:
    load_dotenv()
    init_db()

    token = os.environ.get("TELEGRAM_BOT_TOKEN")
    if not token:
        raise RuntimeError("TELEGRAM_BOT_TOKEN is not set in the environment.")

    app = Application.builder().token(token).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("add", add_feed))
    app.add_handler(CommandHandler("track", track_article))
    app.add_handler(CommandHandler("feeds", list_feeds))
    app.add_handler(CallbackQueryHandler(handle_feedback, pattern=r"^(like|dislike):"))

    logger.info("Bot started. Polling for updates…")
    app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    load_dotenv(verbose=True)
    main()
