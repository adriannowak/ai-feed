# Cloudflare Worker Setup

This Worker relays Telegram button callbacks to GitHub Actions.

## How it works

User clicks 👍/👎 in Telegram
  → Telegram POSTs callback_query to this Worker
  → Worker answers callback instantly (✅ on button)
  → Worker fires GitHub repository_dispatch
  → feedback.yml GH Actions workflow triggers
  → Saves feedback to feed.db and commits back to repo

## Deploy (free, ~2 minutes)

1. Go to https://workers.cloudflare.com - free account, no credit card needed
2. Create a new Worker
3. Paste the contents of cloudflare-worker.js
4. Go to Settings → Variables and add:
   - TELEGRAM_BOT_TOKEN — your bot token from @BotFather
   - GH_PAT — GitHub Personal Access Token with repo scope
   - GITHUB_REPO — e.g. adriannowak/ai-feed
5. Deploy and note your Worker URL (e.g. https://ai-feed.YOUR_NAME.workers.dev)

## Register Telegram webhook (one-time)

curl -X POST "https://api.telegram.org/bot<YOUR_BOT_TOKEN>/setWebhook" \
  -H "Content-Type: application/json" \
  -d '{"url": "https://YOUR_WORKER_URL"}'

## Verify webhook is registered

curl "https://api.telegram.org/bot<YOUR_BOT_TOKEN>/getWebhookInfo"
