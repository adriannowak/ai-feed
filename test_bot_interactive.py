#!/usr/bin/env python3
"""Interactive bot testing - manually trigger specific commands.

This is a quick way to test individual bot commands without running the full bot.

Usage:
    python test_bot_interactive.py
"""
import asyncio
from unittest.mock import AsyncMock, MagicMock

from dotenv import load_dotenv

from bot import add_feed, list_feeds, start, track_article
from db import init_db


def create_test_update(user_id: int = 12345, username: str = "testuser"):
    """Create a mock update/message object."""
    update = MagicMock()
    update.effective_user.id = user_id
    update.effective_user.username = username
    update.message = AsyncMock()
    update.message.reply_text = AsyncMock()
    return update


def create_test_context(args: list[str] = None):
    """Create a mock context object."""
    context = MagicMock()
    context.args = args or []
    return context


async def simulate_start():
    """Simulate: /start"""
    print("\n" + "="*60)
    print("Simulating: /start")
    print("="*60)

    update = create_test_update(user_id=99999, username="testuser")
    context = create_test_context()

    await start(update, context)

    reply = update.message.reply_text.call_args[0][0]
    print(f"\n📱 Bot says:\n{reply}\n")


async def simulate_add(feed_url: str):
    """Simulate: /add <feed_url>"""
    print("\n" + "="*60)
    print(f"Simulating: /add {feed_url}")
    print("="*60)

    update = create_test_update(user_id=99999, username="testuser")
    context = create_test_context([feed_url])

    await add_feed(update, context)

    reply = update.message.reply_text.call_args[0][0]
    print(f"\n📱 Bot says:\n{reply}\n")


async def simulate_feeds():
    """Simulate: /feeds"""
    print("\n" + "="*60)
    print("Simulating: /feeds")
    print("="*60)

    update = create_test_update(user_id=99999, username="testuser")
    context = create_test_context()

    await list_feeds(update, context)

    reply = update.message.reply_text.call_args[0][0]
    print(f"\n📱 Bot says:\n{reply}\n")


async def simulate_track(article_url: str):
    """Simulate: /track <article_url>"""
    print("\n" + "="*60)
    print(f"Simulating: /track {article_url}")
    print("="*60)

    update = create_test_update(user_id=99999, username="testuser")
    context = create_test_context([article_url])

    await track_article(update, context)

    # Track sends multiple messages
    for i, call in enumerate(update.message.reply_text.call_args_list, 1):
        reply = call[0][0]
        print(f"\n📱 Bot message {i}:\n{reply}")
    print()


async def main():
    """Run interactive tests."""
    load_dotenv()
    init_db()

    print("\n" + "🤖 "*20)
    print("BOT COMMAND SIMULATOR")
    print("🤖 "*20)
    print("\nThis simulates user interactions with your bot.\n")

    # Simulate a typical user flow
    await simulate_start()

    await simulate_add("https://blog.vllm.ai/feed.xml")

    await simulate_feeds()

    await simulate_track("https://huggingface.co/blog/inference-update")

    print("="*60)
    print("✅ Simulation complete!")
    print("="*60)
    print("\nTo test with REAL Telegram:")
    print("  1. Make sure TELEGRAM_BOT_TOKEN is set in your .env")
    print("  2. Run: python bot.py")
    print("  3. Open Telegram and message your bot")
    print("  4. Try: /start, /add, /track, /feeds")
    print("="*60 + "\n")


if __name__ == "__main__":
    asyncio.run(main())

