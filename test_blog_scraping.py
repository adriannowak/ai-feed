#!/usr/bin/env python3
"""Test script for scraping blog pages without RSS feeds"""
from ingest import _scrape_blog_index

# Test the blog page you mentioned
test_url = "https://shekkari1999.github.io/blogs.html"

print(f"\n{'='*80}")
print(f"Testing blog scraping for: {test_url}")
print(f"{'='*80}\n")

articles = _scrape_blog_index(test_url)

print(f"\n{'='*80}")
print(f"Results: Found {len(articles)} articles")
print(f"{'='*80}\n")

if articles:
    for i, article in enumerate(articles, 1):
        print(f"{i}. Title: {article['title']}")
        print(f"   URL: {article['url']}")
        print(f"   Source: {article['source']}")
        print(f"   Text length: {len(article['text'])} chars")
        print()
else:
    print("No articles found. Check the logs above for errors.")
