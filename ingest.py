import hashlib
import feedparser
import trafilatura
from datetime import datetime, timezone
from config import FEEDS
from db import item_exists, insert_item


def _make_id(url: str) -> str:
    return hashlib.sha256(url.encode()).hexdigest()[:16]


def _fetch_text(url: str) -> str | None:
    downloaded = trafilatura.fetch_url(url)
    if not downloaded:
        return None
    return trafilatura.extract(
        downloaded,
        include_comments=False,
        include_tables=False,
        no_fallback=False,
    )


def poll_feeds(feed_urls: list[str] | None = None) -> list[dict]:
    """Fetch feeds, return new unseen items.

    Args:
        feed_urls: List of RSS feed URLs to poll. Defaults to FEEDS from config.

    Returns:
        List of new item dicts, each including a ``feed_url`` key indicating
        which feed the item came from.
    """
    urls = feed_urls if feed_urls is not None else FEEDS
    new_items = []
    for feed_url in urls:
        feed = feedparser.parse(feed_url)
        for entry in feed.entries[:10]:
            url = entry.get("link", "")
            if not url or item_exists(url):
                continue

            title = entry.get("title", "")
            published = entry.get("published", datetime.now(timezone.utc).isoformat())
            text = _fetch_text(url) or ""

            item = {
                "id": _make_id(url),
                "url": url,
                "title": title,
                "source": feed.feed.get("title", feed_url),
                "published": published,
                "text": text[:8000],
                "feed_url": feed_url,
            }
            insert_item(item)
            new_items.append(item)
            print(f"[ingest] new: {title[:80]}")

    return new_items
