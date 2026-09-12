"""Hugging Face models via the public Hub API. Covers Models, and Creative
(text-to-image / text-to-video / text-to-audio pipeline tags) with the same
code -- just a different `pipeline_tag` filter."""
from src.schema import make_entity
from src.http_utils import get_with_retry

_API = "https://huggingface.co/api/models"


def fetch_raw(query: str = "", pipeline_tag: str = None, limit: int = 30) -> list:
    params = {"sort": "downloads", "direction": -1, "limit": limit}
    if query:
        params["search"] = query
    if pipeline_tag:
        params["pipeline_tag"] = pipeline_tag
    resp = get_with_retry(_API, params=params)
    if resp is None:
        return []
    return resp.json()[:limit]


def _extract_license(tags: list) -> str:
    for t in tags or []:
        if t.startswith("license:"):
            return t.split(":", 1)[1]
    return "unknown"


def parse(item: dict, entity_type: str = "model", extra_categories: list = None) -> dict:
    model_id = item.get("id") or item.get("modelId", "")
    provider = model_id.split("/")[0] if "/" in model_id else model_id
    tags = item.get("tags", [])
    url = f"https://huggingface.co/{model_id}"
    return make_entity(
        entity_type=entity_type,
        name=model_id,
        description=item.get("pipeline_tag", "") or "",
        url=url,
        categories=["Models"] + list(extra_categories or []),
        source_name="Hugging Face",
        source_url=url,
        metadata={
            "provider": provider,
            "pipeline_tag": item.get("pipeline_tag"),
            "license": _extract_license(tags),
            "downloads": item.get("downloads", 0),
            "likes": item.get("likes", 0),
            "last_modified": item.get("lastModified"),
            "tags": tags[:15],
        },
    )


def run(query: str = "", pipeline_tag: str = None, entity_type: str = "model", extra_categories: list = None, limit: int = 30) -> list:
    raw = fetch_raw(query, pipeline_tag, limit)
    print(f"  [huggingface] search='{query}' pipeline_tag={pipeline_tag} -> {len(raw)} results")
    return [parse(item, entity_type, extra_categories) for item in raw]
