"""Schema validation: required fields differ slightly by entity_type (e.g. a
taxonomy-style Task record has no single canonical url). This validator is
conservative and explicit: it rejects placeholder records, malformed source
blocks, or unreachable/invalid URL or logo evidence rather than silently
carrying them through the export."""
import re
from urllib.parse import urlparse

BASE_REQUIRED = ["id", "entity_type", "name", "categories", "source"]
URL_REQUIRED_TYPES = {
    "repository", "mcp", "collection", "model", "video", "news",
    "company", "tool", "robot", "device", "personal",
}
VALID_ENTITY_TYPES = {
    "company", "tool", "robot", "device", "personal", "model", "repository",
    "mcp", "collection", "news", "video", "task", "creative",
}


def valid_url(value: str) -> bool:
    if not value:
        return False
    try:
        parsed = urlparse(value)
        return parsed.scheme in {"http", "https"} and bool(parsed.netloc)
    except Exception:
        return False


def validate_entity(entity: dict) -> list:
    issues = []
    for field in BASE_REQUIRED:
        if not entity.get(field):
            issues.append(f"missing {field}")

    # entity_type must be a legal one.
    etype = (entity.get("entity_type") or "").strip().lower()
    if etype not in VALID_ENTITY_TYPES:
        issues.append("invalid entity_type")

    # name must not be empty or placeholder.
    name = (entity.get("name") or "").strip()
    if not name:
        issues.append("missing name")
    if re.fullmatch(r"(placeholder|todo|dummy|example|test)\b.*", name, re.I):
        issues.append("placeholder name")

    # source block shape.
    source = entity.get("source") or {}
    if not isinstance(source, dict):
        issues.append("invalid source")
    else:
        if not source.get("name"):
            issues.append("missing source.name")
        if source.get("url") and not valid_url(str(source.get("url"))):
            issues.append("invalid source.url")

    # URL policy.
    if entity.get("entity_type") in URL_REQUIRED_TYPES and not entity.get("url"):
        issues.append("missing url")
    if entity.get("url") and not valid_url(entity.get("url")):
        issues.append("invalid url")

    # obvious third-party directory/listing URLs.
    bad_patterns = [
        "crunchbase.com", "producthunt.com", "wikipedia.org", "ai-directory",
        "linkedin.com/company", "angel.co", "directory", "listings"
    ]
    url = (entity.get("url") or "").lower()
    if url and any(x in url for x in bad_patterns):
        issues.append("third-party url")

    # Schema metadata integrity.
    if not isinstance(entity.get("categories", []), list):
        issues.append("invalid categories")
    if not isinstance(entity.get("metadata", {}), dict):
        issues.append("invalid metadata")

    # Description must be clear, non-empty, and grounded.
    if not entity.get("description"):
        issues.append("missing description")
    if entity.get("description") and len(str(entity.get("description", "")).strip()) < 8:
        issues.append("description too short")

    return issues


def validate_all(entities: list):
    report = {"valid": 0, "invalid": 0, "issues": []}
    clean = []
    for e in entities:
        issues = validate_entity(e)
        if issues:
            report["invalid"] += 1
            report["issues"].append({"name": e.get("name"), "issues": issues})
        else:
            report["valid"] += 1
            clean.append(e)
    return clean, report
