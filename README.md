# AI Feed Reader

Automated AI blog feed reader with personalized Telegram notifications and daily NotebookLM digests.

## How it works

Every hour (GitHub Actions):
- polls RSS feeds
- scores with sentence-transformers + Groq LLM judge
- sends Telegram notifications with 👍/👎 buttons
- commits feed.db back to repo

When you press 👍 or 👎 (instant tick):
- Cloudflare Worker receives Telegram callback
- fires GitHub repository_dispatch
- feedback.yml saves signal to feed.db
- future articles scored against your taste

Every morning 7am UTC (GitHub Actions):
- generates daily brief via Groq Llama
- saves daily_packs/YYYY-MM-DD_brief.md + _sources.csv
- optionally creates NotebookLM notebook via API

## Setup

### 1. Get API keys (all free)

| Key | Where |
|---|---|
| GROQ_API_KEY | https://console.groq.com |
| TELEGRAM_BOT_TOKEN | @BotFather on Telegram |
| TELEGRAM_CHAT_ID | @userinfobot on Telegram |
| GH_PAT | GitHub Settings → Developer settings → Personal access tokens → repo scope |

### 2. Add GitHub secrets

Go to repo → Settings → Secrets and variables → Actions → New repository secret and add:
- GROQ_API_KEY
- TELEGRAM_BOT_TOKEN
- TELEGRAM_CHAT_ID
- GH_PAT

### 3. Deploy Cloudflare Worker

See webhook/README.md for full instructions.

### 4. Register Telegram webhook

curl -X POST "https://api.telegram.org/bot<YOUR_BOT_TOKEN>/setWebhook" \
  -H "Content-Type: application/json" \
  -d '{"url": "https://YOUR_WORKER_URL"}'

### 5. Add your feeds

Edit config.py and add RSS feed URLs to the FEEDS list.

### 6. Test manually

Go to Actions → Poll AI Feeds → Run workflow

## Cost: ~$0/month

| Service | Free tier |
|---|---|
| GitHub Actions | 2000 min/month (private) / unlimited (public) |
| Groq API | free tier — Llama 3.3 70B |
| sentence-transformers | runs on GH runner, free |
| Cloudflare Workers | 100k req/day free |
| Telegram | free |

## How it learns

- Cold start (less than 5 likes): keyword filter → LLM judge with generic AI/ML prompt
- Phase 2 (5+ likes): embedding pre-filter vs your liked items → LLM judge with your real preference profile
- Every 👍/👎 updates the feedback table → profile rebuilds on next run → smarter notifications
