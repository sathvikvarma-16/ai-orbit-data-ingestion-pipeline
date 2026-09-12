"""Common entity schema shared by every source, per the spec's section 4.1."""
import uuid
from datetime import datetime, timezone

# Fixed namespace so uuid5 is deterministic across runs of this project.
_NAMESPACE = uuid.UUID("6f6d5f2a-6e9b-4c3a-9a1a-8f2b1e7c9d10")


def make_id(entity_type: str, name: str, url: str) -> str:
    """Deterministic id: same (type, name, url) always hashes to the same id,
    so re-running the pipeline never creates duplicate records."""
    key = f"{entity_type.strip().lower()}|{name.strip().lower()}|{(url or '').strip().lower()}"
    return str(uuid.uuid5(_NAMESPACE, key))


def make_entity(
    entity_type: str,
    name: str,
    description: str,
    url: str,
    categories: list,
    source_name: str,
    source_url: str,
    metadata: dict = None,
) -> dict:
    """Builds one record matching the spec's common schema, with domain-specific
    fields (section 4.2) nested under `metadata` rather than flattened at the
    top level -- keeps the common schema stable while still carrying rich,
    structured per-type detail. See README 'Technical decisions'."""
    name = (name or "").strip()
    return {
        "id": make_id(entity_type, name, url or source_url),
        "entity_type": entity_type,
        "name": name,
        "description": (description or "").strip(),
        "url": url or "",
        "categories": list(categories or []),
        "source": {"name": source_name, "url": source_url or ""},
        "metadata": metadata or {},
    }


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()
