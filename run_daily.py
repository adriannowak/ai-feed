"""Entrypoint for the daily NotebookLM pack workflow."""
from db import init_db
from notebooklm import create_daily_pack

if __name__ == "__main__":
    init_db()
    create_daily_pack()
