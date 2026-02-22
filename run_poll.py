"""Entrypoint for the hourly GH Actions poll workflow."""
from db import init_db
from ingest import poll_feeds
from ranker import score_item
from notifier import notify_item
from dotenv import load_dotenv

def main():
    init_db()
    new_items = poll_feeds()
    print(f"[poll] {len(new_items)} new items")

    for item in new_items:
        print(item)
        scored = score_item(item)
        if scored:
            print(f"[poll] notifying: {item['title'][:60]} score={scored.get('score')}")
            notify_item(scored)

if __name__ == "__main__":
    load_dotenv()
    main()
