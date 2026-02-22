"""
Called by the feedback GH Actions workflow (repository_dispatch).
Reads ITEM_ID and SIGNAL from env vars, writes to DB.
"""
import os

from dotenv import load_dotenv

from db import init_db, add_feedback


def main():
    init_db()
    item_id = os.environ["ITEM_ID"]
    signal = int(os.environ["SIGNAL"])
    add_feedback(item_id, signal)
    print(f"[feedback] saved: item={item_id} signal={signal:+d}")


if __name__ == "__main__":
    load_dotenv()

    main()
