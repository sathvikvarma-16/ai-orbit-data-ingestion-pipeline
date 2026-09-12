"""Classification: tags each entity's category list based on its own metadata --
recency ("New") and which Task(s) it solves, via a small keyword taxonomy."""
import datetime as dt
from src.schema import make_entity

# Which metadata field carries a "last active" timestamp, per entity_type.
_DATE_FIELDS = {
    "repository": "pushed_at", "mcp": "pushed_at", "collection": "pushed_at",
    "model": "last_modified", "video": "published_at", "news": "published_at",
}

# A small task taxonomy. Keys become Task entities; values are keyword hints
# used to match a Tool/Model/Repo to a Task via its name/description/tags.
TASK_KEYWORDS = {
    "code-generation": ["code", "coding", "programming", "developer"],
    "image-generation": ["image", "text-to-image", "diffusion", "photo"],
    "video-generation": ["video generation", "text-to-video"],
    "audio-generation": ["speech", "voice", "text-to-speech", "music generation"],
    "chat-assistant": ["chat", "assistant", "conversational"],
    "summarization": ["summariz", "summary"],
    "translation": ["translat"],
    "data-analysis": ["data analysis", "analytics", "spreadsheet"],
    "search-research": ["search", "research", "retrieval"],
    "agent-automation": ["agent", "automation", "workflow"],
}


def tag_recency(entity: dict, days: int = 30) -> dict:
    field = _DATE_FIELDS.get(entity["entity_type"])
    raw = entity.get("metadata", {}).get(field) if field else None
    if not raw:
        return entity
    try:
        ts = dt.datetime.fromisoformat(str(raw).replace("Z", "+00:00"))
        now = dt.datetime.now(dt.timezone.utc)
        if (now - ts).days <= days:
            cats = set(entity.get("categories", []))
            cats.add("New")
            entity["categories"] = sorted(cats)
    except (ValueError, TypeError):
        pass
    return entity


def tag_tasks(entity: dict) -> dict:
    haystack = " ".join([
        entity.get("name", ""),
        entity.get("description", ""),
        " ".join(entity.get("categories", [])),
        " ".join(entity.get("metadata", {}).get("tags", []) or []),
        str(entity.get("metadata", {}).get("pipeline_tag", "")),
    ]).lower()
    matched = [task for task, kws in TASK_KEYWORDS.items() if any(k in haystack for k in kws)]
    if matched:
        entity.setdefault("metadata", {})["related_tasks"] = matched
    return entity


def materialize_task_entities() -> list:
    """Turns the taxonomy itself into real Task entities so relationships can
    point at a real id rather than a bare string."""
    return [
        make_entity(
            entity_type="task",
            name=task.replace("-", " ").title(),
            description=f"Things you can do with AI related to {task.replace('-', ' ')}.",
            url="",
            categories=["Tasks"],
            source_name="Manual/Taxonomy",
            source_url="",
            metadata={"slug": task},
        )
        for task in TASK_KEYWORDS
    ]
