import os
import requests
from db import mark_notified

# Telegram message limit is 4096 characters
TELEGRAM_MAX_LENGTH = 4096


def _escape_markdown(text: str) -> str:
    """Escape special characters for Telegram Markdown.

    Telegram uses a modified Markdown that requires escaping these characters:
    _ * [ ] ( ) ~ ` > # + - = | { } . !
    """
    special_chars = ['_', '*', '[', ']', '(', ')', '~', '`', '>', '#', '+', '-', '=', '|', '{', '}', '.', '!']
    for char in special_chars:
        text = text.replace(char, '\\' + char)
    return text

def notify_summary(summary: str):
    BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
    CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID")
    if not BOT_TOKEN or not CHAT_ID:
        raise RuntimeError(
            "Telegram bot not configured. Set TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID in the environment to enable notifications."
        )

    # Split summary if it's too long
    header = "📝 *Daily Summary*\n\n"
    full_text = header + summary

    # If the message fits, send it as-is
    chunks = [full_text]

    for i, chunk in enumerate(chunks):
        if i > 0:
            # Add continuation indicator for subsequent chunks
            chunk = f"_(continued {i+1}/{len(chunks)})_\n\n" + chunk

        # Try sending with Markdown first
        response = requests.post(
            f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage",
            json={
                "chat_id": CHAT_ID,
                "text": chunk,
                "parse_mode": "Markdown",
            }
        )

        # If Markdown parsing fails, retry without parse_mode (plain text)
        if not response.ok:
            error_data = response.json()
            if error_data.get("error_code") == 400 and "parse entities" in error_data.get("description", ""):
                print(f"Markdown parsing failed for chunk {i+1}/{len(chunks)}, retrying as plain text")
                response = requests.post(
                    f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage",
                    json={
                        "chat_id": CHAT_ID,
                        "text": chunk,
                    }
                )

        if not response.ok:
            print(f"Failed to send chunk {i+1}/{len(chunks)}: {response.text}")
        else:
            print(f"Sent chunk {i+1}/{len(chunks)}")

def notify_item(item: dict):
    BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
    CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID")
    if not BOT_TOKEN or not CHAT_ID:
        raise RuntimeError(
            "Telegram bot not configured. Set TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID in the environment to enable notifications."
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
            {
                "text": "👍 Like",
                "callback_data": f"like:{item['id']}"
            },
            {
                "text": "👎 Dislike",
                "callback_data": f"dislike:{item['id']}"
            },
        ]]
    }

    # Try sending with Markdown first
    response = requests.post(
        f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage",
        json={
            "chat_id": CHAT_ID,
            "text": text,
            "parse_mode": "Markdown",
            "reply_markup": keyboard,
        }
    )

    # If Markdown parsing fails, retry without parse_mode (plain text)
    if not response.ok:
        error_data = response.json()
        if error_data.get("error_code") == 400 and "parse entities" in error_data.get("description", ""):
            print(f"Markdown parsing failed for item {item['id']}, retrying as plain text")
            response = requests.post(
                f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage",
                json={
                    "chat_id": CHAT_ID,
                    "text": text,
                    "reply_markup": keyboard,
                }
            )

    if not response.ok:
        print(f"Failed to send notification for item {item['id']}: {response.text}")

    mark_notified(item["id"])
