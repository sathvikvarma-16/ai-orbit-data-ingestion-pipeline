"""Schema validation: required fields differ slightly by entity_type (e.g. a
taxonomy-style Task record has no single canonical url)."""

BASE_REQUIRED = ["id", "entity_type", "name", "categories", "source"]
URL_REQUIRED_TYPES = {
    "repository", "mcp", "collection", "model", "video", "news",
    "company", "tool", "robot", "device", "personal",
}


def validate_entity(entity: dict) -> list:
    issues = []
    for field in BASE_REQUIRED:
        if not entity.get(field):
            issues.append(f"missing {field}")
    if entity.get("entity_type") in URL_REQUIRED_TYPES and not entity.get("url"):
        issues.append("missing url")
    if not entity.get("description"):
        issues.append("missing description")
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
