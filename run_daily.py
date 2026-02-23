"""Entrypoint for the daily NotebookLM pack workflow."""
import os
import requests
from dotenv import load_dotenv

from db import init_db
from notebooklm import create_daily_pack


def _edit_or_send_message(chat_id: int, text: str, message_id: int = None):
    """Edit the processing message or send a new one if no message_id provided."""
    bot_token = os.environ.get("TELEGRAM_BOT_TOKEN")
    if not bot_token or not chat_id:
        return

    if message_id:
        # Edit existing message
        resp = requests.post(
            f"https://api.telegram.org/bot{bot_token}/editMessageText",
            json={"chat_id": chat_id, "message_id": message_id, "text": text},
        )
        if not resp.ok:
            print(f"[daily] Edit failed, sending as new message: {resp.text}")
            # Fallback to new message
            requests.post(
                f"https://api.telegram.org/bot{bot_token}/sendMessage",
                json={"chat_id": chat_id, "text": text},
            )
    else:
        # Send new message
        requests.post(
            f"https://api.telegram.org/bot{bot_token}/sendMessage",
            json={"chat_id": chat_id, "text": text},
        )


if __name__ == "__main__":
    load_dotenv()
    init_db()

    # Get chat_id and message_id if triggered by user command
    chat_id = os.environ.get("CHAT_ID")
    processing_message_id = os.environ.get("PROCESSING_MESSAGE_ID")

    if chat_id and chat_id.isdigit():
        chat_id = int(chat_id)
    else:
        chat_id = None

    if processing_message_id and processing_message_id.isdigit():
        processing_message_id = int(processing_message_id)
    else:
        processing_message_id = None

    try:
        result = create_daily_pack()

        # Send summary if triggered by user command
        if chat_id:
            if result:
                summary = "✅ Daily pack generated successfully!"
            else:
                summary = "⚠️ Daily pack generation completed (check logs for details)"
            _edit_or_send_message(chat_id, summary, processing_message_id)
    except Exception as e:
        print(f"[daily] Error: {e}")
        if chat_id:
            _edit_or_send_message(chat_id, f"❌ Daily pack failed: {e}", processing_message_id)
