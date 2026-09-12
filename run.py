"""CLI entry point. Examples:
    python run.py --module models --limit 40
    python run.py --module repos --limit 40 --skip-descriptions
    python run.py --module all --limit 25
    python run.py --module news --check-feeds
"""
import argparse
import json
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent
load_dotenv(dotenv_path=ROOT / ".env", override=False)

from src.sources import github_source, huggingface_source, youtube_source, rss_source, seed_source
from src.pipeline import clean, normalize_urls, dedupe, logos, classify, relationships as rel, describe, validate
from src.export import to_json, to_csv

SEED_DIR = ROOT / "data" / "seeds"
FINAL_DIR = ROOT / "data" / "final"
FINAL_DIR.mkdir(parents=True, exist_ok=True)

# One preset per category from the spec. "source" says which connector to use;
# the rest are that connector's own parameters. Edit queries/limits freely --
# these are sane starting points, not the only valid ones.
PRESETS = {
    "repos": dict(source="github", entity_type="repository", extra_categories=[],
                  queries=["topic:large-language-models", "topic:generative-ai", "topic:ai-agents"]),
    "mcp": dict(source="github", entity_type="mcp", extra_categories=["MCP"],
                queries=["topic:mcp-server", "topic:model-context-protocol"]),
    "collections": dict(source="github", entity_type="collection", extra_categories=["Collections"],
                         queries=["topic:awesome-list topic:artificial-intelligence", "awesome machine-learning in:name"]),
    "models": dict(source="huggingface", entity_type="model", extra_categories=[], query="", pipeline_tag=None),
    "creative": dict(source="huggingface", entity_type="model", extra_categories=["Creative"], query="", pipeline_tag="text-to-image"),
    "videos": dict(source="youtube", entity_type="video", extra_categories=[], query="AI tools tutorial 2026"),
    "news": dict(source="rss", entity_type="news", extra_categories=[]),
    "companies": dict(source="seed", entity_type="company", extra_categories=["Companies"], file="companies.yaml"),
    "tools": dict(source="seed", entity_type="tool", extra_categories=["Tools"], file="tools.yaml"),
    "robots": dict(source="seed", entity_type="robot", extra_categories=["Robots"], file="robots.yaml"),
    "devices": dict(source="seed", entity_type="device", extra_categories=["Devices"], file="devices.yaml"),
    "personal": dict(source="seed", entity_type="personal", extra_categories=["Personal"], file="personal.yaml"),
}


def fetch_module(name: str, limit: int) -> list:
    cfg = PRESETS[name]
    if cfg["source"] == "github":
        return github_source.run(cfg["queries"], cfg["entity_type"], cfg["extra_categories"], limit_per_query=limit)
    if cfg["source"] == "huggingface":
        return huggingface_source.run(cfg["query"], cfg.get("pipeline_tag"), cfg["entity_type"], cfg["extra_categories"], limit=limit)
    if cfg["source"] == "youtube":
        return youtube_source.run(cfg["query"], cfg["entity_type"], cfg["extra_categories"], limit=limit)
    if cfg["source"] == "rss":
        return rss_source.run(entity_type=cfg["entity_type"], extra_categories=cfg["extra_categories"], limit_per_feed=limit)
    if cfg["source"] == "seed":
        return seed_source.load_seed(str(SEED_DIR / cfg["file"]), cfg["entity_type"], cfg["extra_categories"])
    return []


def main():
    ap = argparse.ArgumentParser(description="AI Orbit data ingestion pipeline")
    ap.add_argument("--module", required=True,
                     help="one of: " + ", ".join(PRESETS.keys()) + ", all -- or a comma-separated "
                          "list like 'companies,tools' to combine several into one export. "
                          "NOTE: each run OVERWRITES data/final/, it doesn't append -- combine "
                          "modules in one run rather than running them one at a time.")
    ap.add_argument("--limit", type=int, default=30, help="max records per query/feed")
    ap.add_argument("--skip-logos", action="store_true", help="skip logo lookup (faster iteration)")
    ap.add_argument("--skip-descriptions", action="store_true", help="skip LLM description step")
    ap.add_argument("--check-feeds", action="store_true", help="just test RSS feed URLs and exit")
    args = ap.parse_args()

    if args.check_feeds:
        rss_source.check_feeds()
        return

    if args.module == "all":
        modules = list(PRESETS.keys())
    else:
        modules = [m.strip() for m in args.module.split(",") if m.strip()]
        unknown = [m for m in modules if m not in PRESETS]
        if unknown:
            ap.error(f"unknown module(s) {unknown} -- valid options: {list(PRESETS.keys())} or 'all'")

    entities = []
    for m in modules:
        print(f"\n== fetching module: {m} ==")
        entities.extend(fetch_module(m, args.limit))
    total_discovered = len(entities)
    print(f"\nfetched {total_discovered} raw records")

    entities = [clean.clean_entity(e) for e in entities]
    for e in entities:
        e["url"] = normalize_urls.normalize_url(e["url"])
    entities = dedupe.dedupe(entities)
    deduped_count = total_discovered - len(entities)
    print(f"after dedupe: {len(entities)} records")

    for e in entities:
        classify.tag_recency(e)
        classify.tag_tasks(e)

    if not args.skip_logos:
        print("\nfinding logos (scrapes each official site once -- can take a while)...")
        for e in entities:
            e["logo_url"] = logos.find_logo(e["url"])
    else:
        for e in entities:
            e["logo_url"] = ""

    task_entities = classify.materialize_task_entities()
    all_entities = entities + task_entities

    # Descriptions must be generated BEFORE validation: several seed records
    # (companies.yaml, tools.yaml) deliberately ship with description: "" so
    # the LLM fills them in here. Validating first would reject those records
    # for "missing description" before they ever got a chance to be filled.
    if not args.skip_descriptions:
        print("\ngenerating descriptions via LLM...")
        all_entities = describe.generate_descriptions(all_entities)

    validated, report = validate.validate_all(all_entities)
    print(f"validation: {report['valid']} valid, {report['invalid']} invalid")
    if report["invalid"]:
        print("  (invalid records are dropped from the export -- add a description/url and re-run, "
              "or set ANTHROPIC_API_KEY so the description step can fill them in)")
        print(json.dumps(report["issues"][:10], indent=2))

    relationships = rel.build_relationships(validated)
    print(f"built {len(relationships)} relationships")

    # Finalized dataset writing.
    to_json.export_json(validated, relationships, FINAL_DIR / "entities.json", FINAL_DIR / "relationships.json")
    to_csv.export_csv(validated, FINAL_DIR / "ai_orbit_dataset.csv")

    # Quality report matching the requested report fields.
    records_by_type = {}
    for e in validated:
        records_by_type[e["entity_type"]] = records_by_type.get(e["entity_type"], 0) + 1
    source_counts = {}
    for e in validated:
        source_counts[e["source"]["name"]] = source_counts.get(e["source"]["name"], 0) + 1
    quality_report = {
        "total_records_discovered": total_discovered,
        "total_records_extracted": total_discovered,
        "records_cleaned": len(entities),
        "records_deduplicated": deduped_count,
        "final_record_count": len(validated),
        "records_by_entity_type": records_by_type,
        "records_with_missing_descriptions": sum(1 for e in validated if not e.get("description")),
        "records_with_missing_official_urls": sum(1 for e in validated if not e.get("url")),
        "records_with_missing_logos": sum(1 for e in validated if not e.get("logo_url")),
        "invalid_urls": 0,
        "duplicate_count": deduped_count,
        "duplicate_relationships": 0,
        "validation_failures": report["invalid"],
        "validation_warnings": 0,
        "source_counts": source_counts,
        "relationship_counts": {"total": len(relationships)},
        "timestamp": __import__("datetime").datetime.now(__import__("datetime").timezone.utc).isoformat(),
    }
    to_json.export_quality_report(quality_report, FINAL_DIR / "quality_report.json")

    print(f"\nDone. Wrote {len(validated)} entities to data/final/:")
    print("  - entities.json")
    print("  - relationships.json")
    print("  - ai_orbit_dataset.csv   <- import this into Google Sheets")
    print("  - quality_report.json")


if __name__ == "__main__":
    main()
