import json


def export_json(entities: list, relationships: list, entities_path, relationships_path) -> None:
    with open(entities_path, "w", encoding="utf-8") as f:
        json.dump(entities, f, indent=2, ensure_ascii=False)
    with open(relationships_path, "w", encoding="utf-8") as f:
        json.dump(relationships, f, indent=2, ensure_ascii=False)
