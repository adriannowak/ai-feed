"""Entrypoint for the daily NotebookLM pack workflow."""
from dotenv import load_dotenv

from db import init_db
from notebooklm import create_daily_pack

if __name__ == "__main__":
    load_dotenv()
    init_db()
    create_daily_pack()
