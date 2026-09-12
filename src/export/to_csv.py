"""Flattens entities into one CSV -- import this straight into Google Sheets
(File > Import > Upload) to satisfy Step 4 of the task."""
import csv
import json

COLUMNS = [
    "id", "entity_type", "name", "description", "url", "logo_url",
    "categories", "source_name", "source_url", "metadata_json",
]


def export_csv(entities: list, path) -> None:
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=COLUMNS)
        writer.writeheader()
        for e in entities:
            writer.writerow({
                "id": e["id"],
                "entity_type": e["entity_type"],
                "name": e["name"],
                "description": e["description"],
                "url": e["url"],
                "logo_url": e.get("logo_url", ""),
                "categories": "; ".join(e.get("categories", [])),
                "source_name": e["source"]["name"],
                "source_url": e["source"]["url"],
                "metadata_json": json.dumps(e.get("metadata", {}), ensure_ascii=False),
            })
