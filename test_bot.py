#!/usr/bin/env python3
"""Test script to simulate Telegram bot commands without running the actual bot.

This allows you to test bot handlers locally by simulating user interactions.

Usage:
    python test_bot.py
"""
import asyncio
import os
from unittest.mock import AsyncMock, MagicMock

from dotenv import load_dotenv

# Import bot functions
from bot import add_feed, handle_feedback, list_feeds, start, track_article
from db import init_db


def create_mock_update(command: str, args: list[str] = None, user_id: int = 123456789, username: str = "testuser"):
    """Create a mock Update object that simulates a Telegram message."""
    update = MagicMock()

    # Mock user
    update.effective_user.id = user_id
    update.effective_user.username = username

    # Mock message
    update.message = AsyncMock()
    update.message.reply_text = AsyncMock()

    return update


def create_mock_context(args: list[str] = None):
    """Create a mock Context object."""
    context = MagicMock()
    context.args = args or []
    return context


def create_mock_callback_query(data: str, user_id: int = 123456789):
    """Create a mock callback query for button clicks (like/dislike)."""
    update = MagicMock()

    # Mock callback query
    update.callback_query = AsyncMock()
    update.callback_query.answer = AsyncMock()
    update.callback_query.edit_message_reply_markup = AsyncMock()
    update.callback_query.data = data
    update.callback_query.from_user.id = user_id

    return update


async def test_start_command():
    """Test /start command."""
    print("\n" + "="*80)
    print("TEST: /start command")
    print("="*80)

    update = create_mock_update("/start")
    context = create_mock_context()

    await start(update, context)

    # Check what was sent to the user
    assert update.message.reply_text.called
    reply = update.message.reply_text.call_args[0][0]
    print(f"✅ Bot response:\n{reply}\n")


async def test_add_feed_valid():
    """Test /add command with a valid RSS feed."""
    print("\n" + "="*80)
    print("TEST: /add <valid_feed_url>")
    print("="*80)

    feed_url = "https://huggingface.co/blog/feed.xml"
    update = create_mock_update("/add", user_id=999)
    context = create_mock_context([feed_url])

    await add_feed(update, context)

    assert update.message.reply_text.called
    reply = update.message.reply_text.call_args[0][0]
    print(f"✅ Bot response:\n{reply}\n")


async def test_add_feed_invalid():
    """Test /add command with an invalid URL."""
    print("\n" + "="*80)
    print("TEST: /add <invalid_url>")
    print("="*80)

    feed_url = "https://invalid-url-that-does-not-exist.com/feed.xml"
    update = create_mock_update("/add")
    context = create_mock_context([feed_url])

    await add_feed(update, context)

    assert update.message.reply_text.called
    reply = update.message.reply_text.call_args[0][0]
    print(f"✅ Bot response:\n{reply}\n")


async def test_add_feed_no_args():
    """Test /add command without arguments."""
    print("\n" + "="*80)
    print("TEST: /add (no arguments)")
    print("="*80)

    update = create_mock_update("/add")
    context = create_mock_context([])

    await add_feed(update, context)

    assert update.message.reply_text.called
    reply = update.message.reply_text.call_args[0][0]
    print(f"✅ Bot response:\n{reply}\n")


async def test_list_feeds():
    """Test /feeds command."""
    print("\n" + "="*80)
    print("TEST: /feeds command")
    print("="*80)

    # First add a user with the start command
    update = create_mock_update("/start", user_id=888)
    context = create_mock_context()
    await start(update, context)

    # Now list feeds
    update = create_mock_update("/feeds", user_id=888)
    context = create_mock_context()

    await list_feeds(update, context)

    assert update.message.reply_text.called
    reply = update.message.reply_text.call_args[0][0]
    print(f"✅ Bot response:\n{reply}\n")


async def test_track_article():
    """Test /track command."""
    print("\n" + "="*80)
    print("TEST: /track <article_url>")
    print("="*80)

    article_url = "https://huggingface.co/blog/inference-update"
    update = create_mock_update("/track", user_id=777)
    context = create_mock_context([article_url])

    await track_article(update, context)

    # Should be called twice (once for "fetching" message, once for result)
    assert update.message.reply_text.called
    print(f"✅ Bot reply_text was called {update.message.reply_text.call_count} time(s)")

    # Print all replies
    for i, call in enumerate(update.message.reply_text.call_args_list, 1):
        reply = call[0][0]
        print(f"   Reply {i}: {reply}")
    print()


async def test_feedback_like():
    """Test 👍 button callback."""
    print("\n" + "="*80)
    print("TEST: Like button (👍)")
    print("="*80)

    item_id = "test_item_123"
    update = create_mock_callback_query(f"like:{item_id}", user_id=666)
    context = create_mock_context()

    await handle_feedback(update, context)

    assert update.callback_query.answer.called
    ack = update.callback_query.answer.call_args
    print(f"✅ Callback answer: {ack}\n")


async def test_feedback_dislike():
    """Test 👎 button callback."""
    print("\n" + "="*80)
    print("TEST: Dislike button (👎)")
    print("="*80)

    item_id = "test_item_456"
    update = create_mock_callback_query(f"dislike:{item_id}", user_id=666)
    context = create_mock_context()

    await handle_feedback(update, context)

    assert update.callback_query.answer.called
    ack = update.callback_query.answer.call_args
    print(f"✅ Callback answer: {ack}\n")


async def main():
    """Run all tests."""
    load_dotenv()
    init_db()

    print("\n" + "🤖 "*20)
    print("TELEGRAM BOT TEST SUITE")
    print("🤖 "*20)

    # Run all tests
    await test_start_command()
    await test_add_feed_no_args()
    await test_add_feed_valid()
    await test_add_feed_invalid()
    await test_list_feeds()
    await test_track_article()
    await test_feedback_like()
    await test_feedback_dislike()

    print("\n" + "="*80)
    print("✅ ALL TESTS COMPLETED")
    print("="*80)
    print("\nNote: These are simulation tests. To test with real Telegram:")
    print("  1. Run: python bot.py")
    print("  2. Message your bot on Telegram")
    print("  3. Try commands: /start, /add, /track, /feeds")
    print("="*80 + "\n")


if __name__ == "__main__":
    asyncio.run(main())

