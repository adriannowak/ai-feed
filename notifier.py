import os
import requests
from db import mark_notified

# Telegram message limit is 4096 characters
TELEGRAM_MAX_LENGTH = 4096


def _escape_markdown(text: str) -> str:
    """Escape special characters for Telegram Markdown."""
    special_chars = [
        "_", "*", "[", "]", "(", ")", "~", "`", ">",
        "#", "+", "-", "=", "|", "{", "}", ".", "!",
    ]
    for char in special_chars:
        text = text.replace(char, "\\" + char)
    return text


def _send_message(bot_token: str, chat_id, text: str, **kwargs) -> requests.Response:
    """Send a Telegram message, falling back to plain text if Markdown fails."""
    payload = {"chat_id": chat_id, "text": text, **kwargs}
    response = requests.post(
        f"https://api.telegram.org/bot{bot_token}/sendMessage",
        json=payload,
    )
    if not response.ok:
        error = response.json()
        if error.get("error_code") == 400 and "parse entities" in error.get("description", ""):
            # Retry without parse_mode
            payload.pop("parse_mode", None)
            response = requests.post(
                f"https://api.telegram.org/bot{bot_token}/sendMessage",
                json=payload,
            )
    return response


def notify_summary(user_id: int, summary: str):
    BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
    if not BOT_TOKEN:
        raise RuntimeError(
            "Telegram bot not configured. Set TELEGRAM_BOT_TOKEN in the environment."
        )

    text = "📝 *Daily Summary*\n\n" + summary
    response = _send_message(BOT_TOKEN, user_id, text, parse_mode="Markdown")
    if not response.ok:
        print(f"Failed to send summary to user={user_id}: {response.text}")


def notify_item(item: dict, user_id: int):
    BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
    if not BOT_TOKEN:
        raise RuntimeError(
            "Telegram bot not configured. Set TELEGRAM_BOT_TOKEN in the environment to enable notifications."
        )

    topics = ", ".join(item.get("topics", []))
    text = (
        f"📰 *{item['title']}*\n"
        f"🔗 {item['url']}\n"
        f"📌 Source: {item.get('source', '')}\n"
        f"🏷 Topics: {topics}\n"
        f"⭐ Score: {item.get('score', '?')}/100\n"
        f"💬 {item.get('reason', '')}"
    )

    keyboard = {
        "inline_keyboard": [[
            {"text": "👍 Like", "callback_data": f"like:{item['id']}"},
            {"text": "👎 Dislike", "callback_data": f"dislike:{item['id']}"},
        ]]
    }

    response = _send_message(
        BOT_TOKEN, user_id, text,
        parse_mode="Markdown",
        reply_markup=keyboard,
    )
    if not response.ok:
        print(f"Failed to send notification for item {item['id']} to user={user_id}: {response.text}")

    mark_notified(user_id, item["id"])
