import hashlib
import logging
from datetime import datetime, timezone
from html.parser import HTMLParser
from urllib.parse import urljoin, urlparse

import feedparser
import trafilatura
from bs4 import BeautifulSoup

from config import FEEDS
from db import item_exists, insert_item

logger = logging.getLogger(__name__)


class _TitleParser(HTMLParser):
    """Minimal HTML parser that extracts the content of the ``<title>`` tag."""

    def __init__(self):
        super().__init__()
        self.title: str | None = None
        self._in_title = False

    def handle_starttag(self, tag, attrs):
        if tag == "title":
            self._in_title = True

    def handle_data(self, data):
        if self._in_title:
            self.title = data.strip()

    def handle_endtag(self, tag):
        if tag == "title":
            self._in_title = False


def _make_id(url: str) -> str:
    return hashlib.sha256(url.encode()).hexdigest()[:16]


def _fetch_text(url: str) -> str | None:
    """Fetch and extract text from a URL. Returns None if fetch or extraction fails."""
    try:
        downloaded = trafilatura.fetch_url(url)
        if not downloaded:
            return None
        return trafilatura.extract(
            downloaded,
            include_comments=False,
            include_tables=False,
            no_fallback=False,
        )
    except Exception as e:
        logger.error("failed to fetch text from %s: %s", url[:80], e)
        return None


def _scrape_page_as_article(url: str, feed_url: str) -> dict | None:
    """Fallback: scrape a page directly as if it's a single article."""
    try:
        if item_exists(url):
            return None

        downloaded = trafilatura.fetch_url(url)
        if not downloaded:
            logger.warning("could not download page %s", url[:80])
            return None

        metadata = trafilatura.extract_metadata(downloaded)
        title = None
        if metadata:
            title = metadata.title or metadata.sitename

        text = trafilatura.extract(
            downloaded,
            include_comments=False,
            include_tables=False,
            no_fallback=False,
        )

        if not text or len(text.strip()) < 100:
            logger.warning("insufficient content from %s", url[:80])
            return None

        if not title:
            parser = _TitleParser()
            try:
                parser.feed(downloaded)
                title = parser.title
            except Exception:
                pass

        if not title:
            title = url.split("/")[-1] or url

        return {
            "id": _make_id(url),
            "url": url,
            "title": title[:200],
            "source": metadata.sitename if metadata and metadata.sitename else url.split("/")[2],
            "published": datetime.now(timezone.utc).isoformat(),
            "text": text[:8000],
            "feed_url": feed_url,
        }

    except Exception as e:
        logger.error("error scraping page %s: %s", url[:80], e)
        return None


def _extract_article_links(html_content: str, base_url: str) -> list[str]:
    """Extract article/blog post links from an HTML page (blog index)."""
    try:
        soup = BeautifulSoup(html_content, "html.parser")
        links = []

        for a_tag in soup.find_all("a", href=True):
            href = a_tag["href"]

            if href.startswith("#") or href.startswith("mailto:") or href.startswith("tel:"):
                continue

            full_url = urljoin(base_url, href)

            if urlparse(full_url).netloc != urlparse(base_url).netloc:
                continue

            link_lower = href.lower()
            text_lower = a_tag.get_text().strip().lower()

            if (
                ("blog" in link_lower or "post" in link_lower or "article" in link_lower)
                and href not in ["/", "/blog", "/blog/", "/blogs.html", "blogs.html"]
                and text_lower not in ["home", "about", "contact", "blog", "blogs", "back"]
            ):
                if full_url not in links and full_url != base_url:
                    links.append(full_url)

        logger.info("found %d potential article links from %s", len(links), base_url[:80])
        return links

    except Exception as e:
        logger.error("error extracting links from %s: %s", base_url[:80], e)
        return []


def _scrape_blog_index(url: str) -> list[dict]:
    """Scrape a blog index page and return articles from linked posts."""
    try:
        downloaded = trafilatura.fetch_url(url)
        if not downloaded:
            logger.warning("could not download blog index %s", url[:80])
            return []

        article_urls = _extract_article_links(downloaded, url)

        if not article_urls:
            logger.info("no article links found, trying single article scrape")
            article = _scrape_page_as_article(url, url)
            return [article] if article else []

        articles = []
        for article_url in article_urls[:10]:
            try:
                article = _scrape_page_as_article(article_url, url)
                if article:
                    articles.append(article)
                    logger.info("scraped article: %s", article["title"][:80])
            except Exception as e:
                logger.error("error scraping article %s: %s", article_url[:80], e)
                continue

        return articles

    except Exception as e:
        logger.error("error processing blog index %s: %s", url[:80], e)
        return []


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
        try:
            feed = feedparser.parse(feed_url)

            if hasattr(feed, "bozo") and feed.bozo:
                logger.warning(
                    "feed parse error for %s: %s",
                    feed_url,
                    feed.get("bozo_exception", "unknown error"),
                )

            if not hasattr(feed, "entries") or len(feed.entries) == 0:
                logger.warning("no entries found in feed %s, trying blog index scrape", feed_url)
                articles = _scrape_blog_index(feed_url)
                for article in articles:
                    insert_item(article)
                    new_items.append(article)
                continue

            for entry in feed.entries[:10]:
                try:
                    url = entry.get("link", "")
                    if not url or item_exists(url):
                        continue

                    title = entry.get("title", "")
                    if not title:
                        logger.warning("skipping entry with no title: %s", url[:80])
                        continue

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
                    logger.info("new: %s", title[:80])

                except Exception as e:
                    logger.error("error processing entry from %s: %s", feed_url, e)
                    continue

        except Exception as e:
            logger.error("error processing feed %s: %s", feed_url, e)
            continue

    return new_items
