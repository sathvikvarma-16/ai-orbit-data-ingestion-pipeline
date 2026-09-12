"""GitHub repositories via the official Search API. Covers Repositories, MCP,
and Collections (awesome-lists) -- same fetch/parse logic, different queries.

NOTE on query syntax: GitHub's search `q` param ANDs multiple qualifiers
together (e.g. "topic:a topic:b" means "has BOTH topics", not "either"), so
OR-style coverage is done here by running one query per topic and letting
dedupe.py merge overlaps -- not by trying to cram "OR" into a single query.
"""
import os
from src.schema import make_entity
from src.http_utils import get_with_retry

_API = "https://api.github.com/search/repositories"


def _headers():
    h = {"Accept": "application/vnd.github+json"}
    token = os.getenv("GITHUB_TOKEN")
    if token:
        h["Authorization"] = f"Bearer {token}"
    return h


def fetch_raw(query: str, limit: int = 30) -> list:
    resp = get_with_retry(
        _API,
        params={"q": query, "sort": "stars", "order": "desc", "per_page": min(limit, 50)},
        headers=_headers(),
    )
    if resp is None:
        return []
    return resp.json().get("items", [])[:limit]


def parse(item: dict, entity_type: str, extra_categories: list = None) -> dict:
    # Prefer the project's own homepage over its GitHub page when it has one --
    # that's usually the actual vendor/official site (see README).
    url = item.get("homepage") or item.get("html_url", "")
    owner = (item.get("owner") or {}).get("login")
    license_info = item.get("license") or {}
    return make_entity(
        entity_type=entity_type,
        name=item.get("full_name") or item.get("name", ""),
        description=item.get("description") or "",
        url=url,
        categories=["Repositories"] + list(extra_categories or []),
        source_name="GitHub",
        source_url=item.get("html_url", ""),
        metadata={
            "stars": item.get("stargazers_count", 0),
            "language": item.get("language"),
            "pushed_at": item.get("pushed_at"),
            "topics": item.get("topics", []),
            "owner": owner,
            "owner_avatar": (item.get("owner") or {}).get("avatar_url"),
            "license": license_info.get("name"),
        },
    )


def run(queries: list, entity_type: str = "repository", extra_categories: list = None, limit_per_query: int = 30) -> list:
    entities = []
    for q in queries:
        raw = fetch_raw(q, limit_per_query)
        print(f"  [github] '{q}' -> {len(raw)} results")
        entities.extend(parse(item, entity_type, extra_categories) for item in raw)
    return entities
