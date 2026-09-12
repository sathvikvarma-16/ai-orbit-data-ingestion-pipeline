"""Step 3 of the task: use an LLM to generate one clean description per record,
grounded only in facts already collected (no invented details). Falls back to
the source's own description when no API key is set, so the pipeline never
hard-fails on this step."""
import os
import time
from concurrent.futures import ThreadPoolExecutor, as_completed

try:
    from anthropic import Anthropic
except ImportError:
    Anthropic = None

MODEL = os.getenv("DESCRIPTION_MODEL", "claude-sonnet-5")

_PROMPT = """You are writing one catalog description for an AI-ecosystem directory.

Entity type: {entity_type}
Name: {name}
Known facts: {facts}

Write ONE description, 1-2 sentences, under 40 words. Use ONLY the facts given --
do not invent details you were not given. No marketing language ("revolutionary",
"cutting-edge", "game-changing"). Do not start with "{name} is..." or "This is...".
Return ONLY the description text, nothing else."""


def _describe_one(client, entity: dict) -> str:
    facts = entity.get("description", "")
    meta = entity.get("metadata", {})
    facts_str = f"{facts} | metadata: {meta}"[:800] if meta else facts[:800]
    prompt = _PROMPT.format(entity_type=entity["entity_type"], name=entity["name"], facts=facts_str)
    try:
        resp = client.messages.create(
            model=MODEL,
            max_tokens=120,
            messages=[{"role": "user", "content": prompt}],
        )
        text = "".join(block.text for block in resp.content if block.type == "text").strip()
        return text or entity.get("description", "")
    except Exception as exc:  # noqa: BLE001 -- any API failure should degrade, not crash the run
        print(f"    [describe] failed for '{entity['name']}': {exc}")
        return entity.get("description", "")


def generate_descriptions(entities: list, max_workers: int = 6) -> list:
    api_key = os.getenv("ANTHROPIC_API_KEY")
    if not api_key or Anthropic is None:
        print("    no ANTHROPIC_API_KEY set (or `anthropic` not installed) -- keeping original descriptions")
        return entities

    client = Anthropic(api_key=api_key)
    with ThreadPoolExecutor(max_workers=max_workers) as pool:
        futures = {pool.submit(_describe_one, client, e): e for e in entities}
        done = 0
        for fut in as_completed(futures):
            entity = futures[fut]
            entity["description"] = fut.result()
            done += 1
            if done % 25 == 0:
                print(f"    described {done}/{len(entities)}...")
            time.sleep(0.02)
    return entities
