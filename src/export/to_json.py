import json
from datetime import datetime, timezone


def export_json(entities: list, relationships: list, entities_path, relationships_path) -> None:
    with open(entities_path, "w", encoding="utf-8") as f:
        json.dump(entities, f, indent=2, ensure_ascii=False)
    with open(relationships_path, "w", encoding="utf-8") as f:
        json.dump(relationships, f, indent=2, ensure_ascii=False)


def export_quality_report(report: dict, quality_path) -> None:
    # Ensure the report is always timestamped in UTC and written in the same
    # canonical format the rest of the dataset uses.
    report = dict(report)
    report.setdefault("timestamp", datetime.now(timezone.utc).isoformat())
    with open(quality_path, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2, ensure_ascii=False)
