FEEDS = [
    "https://huggingface.co/blog/feed.xml",
    "https://blog.vllm.ai/feed.xml",
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
