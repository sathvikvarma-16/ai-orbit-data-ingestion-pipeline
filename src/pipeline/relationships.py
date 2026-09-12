"""Relationship mapping: derives the edges the spec asks for (section 5) using
simple, explainable heuristics. Best-effort -- spot-check before submitting."""


def _index_by_type(entities):
    by_type = {}
    for e in entities:
        by_type.setdefault(e["entity_type"], []).append(e)
    return by_type


def _find_company(companies, owner_name):
    if not owner_name:
        return None
    owner_norm = owner_name.lower()
    for c in companies:
        c_norm = c["name"].lower()
        if c_norm in owner_norm or owner_norm in c_norm:
            return c
    return None


def build_relationships(entities: list) -> list:
    rels = []
    by_type = _index_by_type(entities)
    companies = by_type.get("company", [])

    # Company --develops--> anything else (repo/model/mcp owner+provider come
    # from the API sources; "maker" is the equivalent field used in the
    # manually-seeded companies/tools/devices/personal YAML).
    for e in entities:
        if e["entity_type"] in ("company", "task"):
            continue
        meta = e.get("metadata", {})
        owner = meta.get("owner") or meta.get("provider") or meta.get("maker")
        company = _find_company(companies, owner)
        if company:
            rels.append({"from": company["id"], "relation": "develops", "to": e["id"]})

    # Tool/Model/Repository --solves--> Task
    task_lookup = {t.get("metadata", {}).get("slug"): t["id"] for t in by_type.get("task", [])}
    for e in entities:
        for task_slug in e.get("metadata", {}).get("related_tasks", []):
            task_id = task_lookup.get(task_slug)
            if task_id:
                rels.append({"from": e["id"], "relation": "solves", "to": task_id})

    # MCP --integrates_with--> Tool/Model (name mention in the MCP's own text)
    for mcp in by_type.get("mcp", []):
        text = f"{mcp['name']} {mcp.get('description', '')}".lower()
        for tool in by_type.get("tool", []) + by_type.get("model", []):
            if tool["name"].lower() in text:
                rels.append({"from": mcp["id"], "relation": "integrates_with", "to": tool["id"]})

    # Device --runs--> Model (only when declared explicitly in the seed data,
    # since this isn't reliably derivable from any API)
    for device in by_type.get("device", []):
        runs_model_name = device.get("metadata", {}).get("runs_model")
        if not runs_model_name:
            continue
        for model in by_type.get("model", []):
            if model["name"].lower() == str(runs_model_name).lower():
                rels.append({"from": device["id"], "relation": "runs", "to": model["id"]})

    return rels
