"""AI news via RSS. Feed URLs verified live as of Sep 2026 -- if one goes
stale later, `check_feeds()` (called via `--check-feeds`) will flag it instead
of failing silently.

`feedparser` is imported lazily inside the functions that need it, so this
module (and its pure `parse()`) stays importable/testable even in an
environment where the package isn't installed yet."""
from src.schema import make_entity

DEFAULT_FEEDS = {
    "TechCrunch AI": "https://techcrunch.com/category/artificial-intelligence/feed/",
    "VentureBeat AI": "https://venturebeat.com/category/ai/feed/",
    "MIT Technology Review": "https://www.technologyreview.com/feed/",
    "The Verge AI": "https://www.theverge.com/ai-artificial-intelligence/rss/index.xml",
    "Hugging Face Blog": "https://huggingface.co/blog/feed.xml",
    "OpenAI News": "https://openai.com/news/rss.xml",
}


def check_feeds(feeds: dict = None) -> None:
    import feedparser
    feeds = feeds or DEFAULT_FEEDS
    for name, url in feeds.items():
        parsed = feedparser.parse(url)
        status = "OK" if parsed.entries else "EMPTY/FAILED"
        print(f"  [rss check] {name}: {status} ({len(parsed.entries)} entries) - {url}")


def fetch_raw(feeds: dict = None, limit_per_feed: int = 20) -> list:
    import feedparser
    feeds = feeds or DEFAULT_FEEDS
    out = []
    for source_name, url in feeds.items():
        parsed = feedparser.parse(url)
        entries = parsed.entries[:limit_per_feed]
        if not entries:
            print(f"  [rss] {source_name}: 0 entries -- feed may be stale, check the URL")
            continue
        print(f"  [rss] {source_name} -> {len(entries)} entries")
        out.extend((source_name, url, entry) for entry in entries)
    return out


def parse(source_name: str, feed_url: str, entry, entity_type: str = "news", extra_categories: list = None) -> dict:
    return make_entity(
        entity_type=entity_type,
        name=entry.get("title", ""),
        description=entry.get("summary", "") or entry.get("description", ""),
        url=entry.get("link", ""),
        categories=["News"] + list(extra_categories or []),
        source_name=source_name,
        source_url=feed_url,
        metadata={"published_at": entry.get("published", "")},
    )


def run(feeds: dict = None, entity_type: str = "news", extra_categories: list = None, limit_per_feed: int = 20) -> list:
    raw = fetch_raw(feeds, limit_per_feed)
    return [parse(sn, fu, e, entity_type, extra_categories) for sn, fu, e in raw]
