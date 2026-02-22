import os

# Invite-only allowlist — comma-separated Telegram user IDs.
# Only users whose ID is in this set can interact with the bot.
# Example: ALLOWED_USER_IDS=123456789,987654321
# Leave empty (or unset) to deny everyone until you add IDs.
_raw = os.environ.get("ALLOWED_USER_IDS", "")
ALLOWED_USER_IDS: frozenset[int] = frozenset(
    int(uid.strip()) for uid in _raw.split(",") if uid.strip().isdigit()
)

FEEDS = [
    "https://huggingface.co/blog/feed.xml",
    "https://blog.vllm.ai/feed.xml",
    "https://shekkari1999.github.io/blogs.html",  # Blog page without RSS feed (will be scraped)
    # "https://bair.berkeley.edu/blog/feed.xml",
    # add more here
]

POLL_INTERVAL_MINUTES = 60
DAILY_DIGEST_HOUR = 8  # 8am UTC

# Scoring thresholds
EMBEDDING_SIMILARITY_THRESHOLD = 0.65
LLM_SCORE_THRESHOLD = 65
DAILY_PACK_MIN_SCORE = 70
DAILY_PACK_MAX_ITEMS = 15

# Cold start keyword filter (used until you have 10+ likes)
COLD_START_KEYWORDS = [
    "vllm", "llm", "inference", "quantization", "kv cache",
    "speculative decoding", "rag", "agents", "fine-tuning",
    "benchmark", "transformer", "embeddings", "serving",
]
