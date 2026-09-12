"""Loader for the manually-curated categories that have no single clean API
(Companies, Tools, Robots, Devices, Personal). YAML in data/seeds/ -- add real
entries there via your own research; this just turns rows into entities."""
import yaml
from pathlib import Path
from src.schema import make_entity


def load_seed(path: str, entity_type: str, extra_categories: list = None) -> list:
    p = Path(path)
    if not p.exists():
        print(f"  [seed] {path} not found -- skipping")
        return []

    with open(p, "r", encoding="utf-8") as f:
        raw_items = yaml.safe_load(f) or []

    entities = []
    for item in raw_items:
        name = (item.get("name") or "").strip()
        if not name:
            continue
        url = item.get("url", "")
        metadata = {k: v for k, v in item.items() if k not in ("name", "url", "description")}
        entities.append(
            make_entity(
                entity_type=entity_type,
                name=name,
                description=item.get("description", ""),
                url=url,
                categories=list(extra_categories or []),
                source_name="Manual/Research",
                source_url=url,
                metadata=metadata,
            )
        )
    print(f"  [seed] {path} -> {len(entities)} records")
    return entities
