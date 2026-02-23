"""Entrypoint for the hourly GH Actions poll workflow."""
import os
import requests
from db import init_db, get_all_users, get_user_feeds
from ingest import poll_feeds
from ranker import score_item
from notifier import notify_item
from dotenv import load_dotenv


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
            print(f"[poll] Edit failed, sending as new message: {resp.text}")
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


def main():
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

    users = get_all_users()
    if not users:
        print("[poll] No users registered yet")
        if chat_id:
            _edit_or_send_message(chat_id, "⚠️ No users registered yet", processing_message_id)
        return

    # Collect all unique feed URLs across all users and remember per-user sets
    user_feeds_map: dict[int, set[str]] = {}
    all_feed_urls: set[str] = set()
    for user in users:
        user_id = user["user_id"]
        feeds = set(get_user_feeds(user_id))
        user_feeds_map[user_id] = feeds
        all_feed_urls.update(feeds)

    # Ingest all unique feeds once (deduped globally by item URL)
    new_items = poll_feeds(list(all_feed_urls))
    print(f"[poll] {len(new_items)} new items ingested across {len(all_feed_urls)} feeds")

    # Score and notify each user only for items from feeds they subscribe to
    total_notifications = 0
    for user in users:
        user_id = user["user_id"]
        user_feed_set = user_feeds_map[user_id]
        user_items = [item for item in new_items if item.get("feed_url") in user_feed_set]

        for item in user_items:
            print(item)
            scored = score_item(item, user_id)
            if scored:
                print(
                    f"[poll] notifying user={user_id}: "
                    f"{item['title'][:60]} score={scored.get('score')}"
                )
                notify_item(scored, user_id)
                total_notifications += 1

    # Send summary if triggered by user command
    if chat_id:
        summary = (
            f"✅ Poll complete!\n\n"
            f"📥 {len(new_items)} new articles found\n"
            f"📢 {total_notifications} notifications sent"
        )
        _edit_or_send_message(chat_id, summary, processing_message_id)


if __name__ == "__main__":
    load_dotenv()
    main()
