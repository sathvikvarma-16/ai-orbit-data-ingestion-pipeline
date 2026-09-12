"""YouTube videos via the official YouTube Data API v3 (search.list)."""
import os
from src.schema import make_entity
from src.http_utils import get_with_retry

_API = "https://www.googleapis.com/youtube/v3/search"


def fetch_raw(query: str, limit: int = 25) -> list:
    key = os.getenv("YOUTUBE_API_KEY")
    if not key:
        print("  [youtube] no YOUTUBE_API_KEY set -- skipping this module")
        return []
    params = {
        "part": "snippet", "q": query, "type": "video",
        "maxResults": min(limit, 50), "order": "relevance", "key": key,
    }
    resp = get_with_retry(_API, params=params)
    if resp is None:
        return []
    return resp.json().get("items", [])[:limit]


def parse(item: dict, entity_type: str = "video", extra_categories: list = None) -> dict:
    video_id = item.get("id", {}).get("videoId", "")
    snippet = item.get("snippet", {})
    url = f"https://www.youtube.com/watch?v={video_id}"
    return make_entity(
        entity_type=entity_type,
        name=snippet.get("title", ""),
        description=snippet.get("description", ""),
        url=url,
        categories=["Videos"] + list(extra_categories or []),
        source_name="YouTube",
        source_url=url,
        metadata={
            "channel": snippet.get("channelTitle"),
            "published_at": snippet.get("publishedAt"),
            "thumbnail": (snippet.get("thumbnails", {}).get("high") or {}).get("url"),
        },
    )


def run(query: str, entity_type: str = "video", extra_categories: list = None, limit: int = 25) -> list:
    raw = fetch_raw(query, limit)
    print(f"  [youtube] '{query}' -> {len(raw)} results")
    return [parse(item, entity_type, extra_categories) for item in raw]
