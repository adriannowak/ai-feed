import os
import requests
from db import mark_notified

BOT_TOKEN = os.environ["TELEGRAM_BOT_TOKEN"]
CHAT_ID = os.environ["TELEGRAM_CHAT_ID"]


def notify_item(item: dict):
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
