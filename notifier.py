import os
import requests
from db import mark_notified


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

    requests.post(
        f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage",
        json={
            "chat_id": CHAT_ID,
            "text": text,
            "parse_mode": "Markdown",
            "reply_markup": keyboard,
        }
    )
    mark_notified(item["id"])
