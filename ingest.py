import hashlib
import feedparser
import trafilatura
from datetime import datetime, timezone
from config import FEEDS
from db import item_exists, insert_item
from bs4 import BeautifulSoup
from urllib.parse import urljoin, urlparse


def _make_id(url: str) -> str:
    return hashlib.sha256(url.encode()).hexdigest()[:16]


def _fetch_text(url: str) -> str | None:
    """Fetch and extract text from a URL. Returns None if fetch or extraction fails."""
    try:
        downloaded = trafilatura.fetch_url(url)
        if not downloaded:
            return None
        extracted = trafilatura.extract(
            downloaded,
            include_comments=False,
            include_tables=False,
            no_fallback=False,
        )
        return extracted
    except Exception as e:
        print(f"[ingest] failed to fetch text from {url[:80]}: {e}")
        return None


def _scrape_page_as_article(url: str) -> dict | None:
    """Fallback: scrape a page directly as if it's a single article (for pages without feeds)."""
    try:
        if item_exists(url):
            return None

        downloaded = trafilatura.fetch_url(url)
        if not downloaded:
            print(f"[ingest] could not download page {url[:80]}")
            return None

        # Try to extract metadata
        metadata = trafilatura.extract_metadata(downloaded)
        title = None
        if metadata:
            title = metadata.title or metadata.sitename

        # Extract text content
        text = trafilatura.extract(
            downloaded,
            include_comments=False,
            include_tables=False,
            no_fallback=False,
        )

        if not text or len(text.strip()) < 100:
            print(f"[ingest] insufficient content from {url[:80]}")
            return None

        # Use metadata or fallback to URL-based title
        if not title:
            # Try to get title from the HTML directly
            from html.parser import HTMLParser
            class TitleParser(HTMLParser):
                def __init__(self):
                    super().__init__()
                    self.title = None
                    self.in_title = False

                def handle_starttag(self, tag, attrs):
                    if tag == 'title':
                        self.in_title = True

                def handle_data(self, data):
                    if self.in_title:
                        self.title = data.strip()

                def handle_endtag(self, tag):
                    if tag == 'title':
                        self.in_title = False

            parser = TitleParser()
            try:
                parser.feed(downloaded)
                title = parser.title
            except:
                pass

        if not title:
            title = url.split('/')[-1] or url

        item = {
            "id": _make_id(url),
            "url": url,
            "title": title[:200],
            "source": metadata.sitename if metadata and metadata.sitename else url.split('/')[2],
            "published": datetime.now(timezone.utc).isoformat(),
            "text": text[:8000],
        }
        return item

    except Exception as e:
        print(f"[ingest] error scraping page {url[:80]}: {e}")
        return None


def _extract_article_links(html_content: str, base_url: str) -> list[str]:
    """Extract article/blog post links from an HTML page (blog index)."""
    try:
        soup = BeautifulSoup(html_content, 'html.parser')
        links = []

        # Look for links in common blog patterns
        for a_tag in soup.find_all('a', href=True):
            href = a_tag['href']

            # Skip external links, anchors, and non-article links
            if href.startswith('#') or href.startswith('mailto:') or href.startswith('tel:'):
                continue

            # Convert relative URLs to absolute
            full_url = urljoin(base_url, href)

            # Only include links from the same domain
            if urlparse(full_url).netloc != urlparse(base_url).netloc:
                continue

            # Common patterns for blog posts (adjust as needed)
            link_lower = href.lower()
            text_lower = a_tag.get_text().strip().lower()

            # Heuristics for blog post links:
            # - Contains "blog", "post", "article" in path
            # - Has meaningful text (not just "home", "about", etc.)
            # - Avoid navigation links
            if (('blog' in link_lower or 'post' in link_lower or 'article' in link_lower) and
                href not in ['/', '/blog', '/blog/', '/blogs.html', 'blogs.html'] and
                text_lower not in ['home', 'about', 'contact', 'blog', 'blogs', 'back']):

                if full_url not in links and full_url != base_url:
                    links.append(full_url)

        print(f"[ingest] found {len(links)} potential article links from {base_url[:80]}")
        return links

    except Exception as e:
        print(f"[ingest] error extracting links from {base_url[:80]}: {e}")
        return []


def _scrape_blog_index(url: str) -> list[dict]:
    """Scrape a blog index page and return articles from linked posts."""
    try:
        downloaded = trafilatura.fetch_url(url)
        if not downloaded:
            print(f"[ingest] could not download blog index {url[:80]}")
            return []

        # Extract article links from the index page
        article_urls = _extract_article_links(downloaded, url)

        if not article_urls:
            print(f"[ingest] no article links found, trying single article scrape")
            # Fallback to treating it as a single article
            article = _scrape_page_as_article(url)
            return [article] if article else []

        # Scrape each article
        articles = []
        for article_url in article_urls[:10]:  # Limit to 10 most recent
            try:
                article = _scrape_page_as_article(article_url)
                if article:
                    articles.append(article)
                    print(f"[ingest] scraped article: {article['title'][:80]}")
            except Exception as e:
                print(f"[ingest] error scraping article {article_url[:80]}: {e}")
                continue

        return articles

    except Exception as e:
        print(f"[ingest] error processing blog index {url[:80]}: {e}")
        return []


def poll_feeds() -> list[dict]:
    """Fetch all feeds, return new unseen items."""
    new_items = []
    for feed_url in FEEDS:
        try:
            feed = feedparser.parse(feed_url)

            # Check if the feed was parsed successfully
            if hasattr(feed, 'bozo') and feed.bozo:
                # bozo=1 means the feed had issues parsing
                print(f"[ingest] warning: feed parse error for {feed_url}: {feed.get('bozo_exception', 'unknown error')}")
                # Continue anyway - feedparser is forgiving and may have partial data

            if not hasattr(feed, 'entries') or len(feed.entries) == 0:
                print(f"[ingest] warning: no entries found in feed {feed_url}, trying blog index scrape")
                # Fallback: try to scrape as blog index page (extract article links)
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
                        print(f"[ingest] skipping entry with no title: {url[:80]}")
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
                    }
                    insert_item(item)
                    new_items.append(item)
                    print(f"[ingest] new: {title[:80]}")

                except Exception as e:
                    print(f"[ingest] error processing entry from {feed_url}: {e}")
                    continue

        except Exception as e:
            print(f"[ingest] error processing feed {feed_url}: {e}")
            continue

    return new_items
