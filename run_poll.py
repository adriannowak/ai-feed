"""Entrypoint for the hourly GH Actions poll workflow."""
from db import init_db, get_all_users, get_user_feeds
from ingest import poll_feeds
from ranker import score_item
from notifier import notify_item
from dotenv import load_dotenv


def main():
    init_db()

    users = get_all_users()
    if not users:
        print("[poll] No users registered yet")
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


if __name__ == "__main__":
    load_dotenv()
    main()
