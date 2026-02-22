# Testing Your Telegram Bot

## 📋 Overview

There are **three ways** to test your Telegram bot:

1. **Mock Testing** (fastest, no real bot needed)
2. **Interactive Simulation** (quick command testing)
3. **Real Telegram Testing** (full end-to-end testing)

---

## 🧪 Method 1: Mock Testing (Automated)

**What it does:** Runs automated tests simulating all bot commands and callbacks.

**Usage:**
```bash
python test_bot.py
```

**Tests included:**
- ✅ `/start` - User registration
- ✅ `/add <url>` - Valid RSS feed
- ✅ `/add <url>` - Invalid URL
- ✅ `/add` - No arguments (error handling)
- ✅ `/feeds` - List subscriptions
- ✅ `/track <url>` - Track article
- ✅ 👍 Like button callback
- ✅ 👎 Dislike button callback

**Output:** Shows what the bot would reply to each command.

---

## 🎮 Method 2: Interactive Simulation

**What it does:** Simulates a typical user interaction flow step by step.

**Usage:**
```bash
python test_bot_interactive.py
```

**Simulates:**
1. User sends `/start`
2. User adds a feed with `/add`
3. User lists feeds with `/feeds`
4. User tracks an article with `/track`

**Advantage:** Easier to understand than automated tests, shows realistic flow.

---

## 📱 Method 3: Real Telegram Testing

**What it does:** Tests with the actual Telegram app and your bot.

### Prerequisites:

1. **Create a bot** (if you haven't):
   - Message [@BotFather](https://t.me/botfather) on Telegram
   - Send `/newbot`
   - Follow instructions to get your `TELEGRAM_BOT_TOKEN`

2. **Add token to .env**:
   ```bash
   TELEGRAM_BOT_TOKEN=123456789:ABCdefGHIjklMNOpqrsTUVwxyz
   ```

### Run the bot:

```bash
python bot.py
```

### Test commands in Telegram:

1. **Start the bot:**
   ```
   /start
   ```
   Expected: Welcome message + auto-subscription to default feeds

2. **Add a new feed:**
   ```
   /add https://example.com/feed.xml
   ```
   Expected: Confirmation message with feed title

3. **List your feeds:**
   ```
   /feeds
   ```
   Expected: List of all subscribed feeds

4. **Track an article:**
   ```
   /track https://example.com/article
   ```
   Expected: "Fetching..." then "Tracking article..." confirmation

5. **Test feedback buttons:**
   - Receive an article with 👍/👎 buttons
   - Click a button
   - Expected: Button acknowledgment and keyboard disappears

---

## 🔍 Understanding Mock Objects

The test scripts use **mock objects** to simulate Telegram's Update and Context objects:

### Mock Update Object:
```python
update.effective_user.id       # User's Telegram ID
update.effective_user.username # User's username
update.message.reply_text()    # Bot's reply method
```

### Mock Context Object:
```python
context.args  # Command arguments (e.g., ["https://feed.xml"])
```

### Mock Callback Query:
```python
update.callback_query.data     # Button data (e.g., "like:item_id")
update.callback_query.answer() # Acknowledge button click
```

---

## 🐛 Common Issues

### Issue: "TELEGRAM_BOT_TOKEN is not set"
**Solution:** Create a `.env` file with your token:
```bash
echo "TELEGRAM_BOT_TOKEN=your_token_here" > .env
```

### Issue: "Module not found: telegram"
**Solution:** Install python-telegram-bot:
```bash
pip install python-telegram-bot
```

### Issue: Database errors in feedback tests
**Note:** This is expected if your database schema doesn't have multi-user support yet. The other tests will still work.

---

## 📝 Quick Test Examples

### Test a single command:

```python
import asyncio
from test_bot_interactive import simulate_start, init_db
from dotenv import load_dotenv

async def quick_test():
    load_dotenv()
    init_db()
    await simulate_start()

asyncio.run(quick_test())
```

### Test with your own feed:

```python
import asyncio
from test_bot_interactive import simulate_add, init_db
from dotenv import load_dotenv

async def test_my_feed():
    load_dotenv()
    init_db()
    await simulate_add("https://your-blog.com/feed.xml")

asyncio.run(test_my_feed())
```

---

## 🎯 Best Practices

1. **Start with mock tests** - Fast feedback, no setup needed
2. **Use interactive simulation** - Understand user flow
3. **Finish with real Telegram** - Full integration testing

---

## 📊 Test Output Examples

### ✅ Successful /start:
```
📱 Bot says:
Welcome! 🎉

Use /add <rss_url> to subscribe to additional feeds.
Use /track <article_url> to seed your taste profile with a specific article.

You are now subscribed to 3 default feed(s).
```

### ✅ Successful /add:
```
📱 Bot says:
✅ Subscribed to *Hugging Face - Blog*
```

### ❌ Invalid feed:
```
📱 Bot says:
⚠️ Could not parse a valid RSS feed at:
https://invalid-url.com/feed.xml

Please check the URL and try again.
```

---

## 🚀 Next Steps

After testing locally:
1. Deploy your bot (see main README)
2. Set up webhooks (optional, for production)
3. Monitor bot logs for real user interactions
4. Add more commands as needed

Happy testing! 🤖

