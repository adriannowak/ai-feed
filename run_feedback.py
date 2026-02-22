"""
Called by the feedback GH Actions workflow (repository_dispatch).
Reads USER_ID, ITEM_ID and SIGNAL from env vars, writes to DB.
"""
import os

from dotenv import load_dotenv

from db import init_db, save_feedback


def main():
    init_db()
    user_id = int(os.environ["USER_ID"])
    item_id = os.environ["ITEM_ID"]
    signal = int(os.environ["SIGNAL"])
    save_feedback(user_id, item_id, signal)
    print(f"[feedback] saved: user={user_id} item={item_id} signal={signal:+d}")


if __name__ == "__main__":
    load_dotenv()

    main()
