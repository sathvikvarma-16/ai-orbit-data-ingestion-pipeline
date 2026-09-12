"""Step 3 of the task: use Gemini to generate one clean description per record,
grounded only in facts already collected (no invented details). Falls back to
the source's own description when no API key is set, so the pipeline never
hard-fails on this step."""
import os
import re
import time
from concurrent.futures import ThreadPoolExecutor, as_completed

try:
    from google import genai
    from google.genai.errors import APIError
except ImportError:
    genai = None
    APIError = Exception

MODEL = os.getenv("DESCRIPTION_MODEL", "gemini-3.6-flash")

_PROMPT = """You are writing one catalog description for an AI-ecosystem directory.

Entity type: {entity_type}
Name: {name}
Known facts: {facts}

Write ONE description, 1-2 sentences, under 40 words. Use ONLY the facts given --
do not invent details you were not given. No marketing language ("revolutionary",
"cutting-edge", "game-changing"). Do not start with "{name} is..." or "This is...".
Return ONLY the description text, nothing else."""


def _needs_gemini_description(entity: dict) -> bool:
    """Only send a Gemini request when the record has a usable source
    description to improve. If the record is blank, keep the original source
    description unchanged so we never invent a description from no facts."""
    facts = (entity.get("description") or "").strip()
    if not facts:
        return False
    # Avoid making Gemini requests for records that already have a useful
    # grounded description; keep the original source description and skip
    # the extra request instead of sending one request per entity.
    return len(facts) < 80


def _parse_retry_delay(value) -> float | None:
    """Turn a Gemini `RetryInfo` string/object into a float delay.
    Accepts values like '51s' and {'seconds': 51, 'nanos': 0}."""
    if isinstance(value, (int, float)):
        return max(float(value), 0.0)
    if isinstance(value, dict):
        seconds = value.get("seconds")
        nanos = value.get("nanos", 0)
        if seconds is not None:
            return max(float(seconds) + (float(nanos) / 1_000_000_000), 0.0)
    if isinstance(value, str):
        value = value.strip()
        match = re.search(r"([0-9]+(?:\.[0-9]+)?)\s*s", value)
        if match:
            return max(float(match.group(1)), 0.0)
    return None


def _extract_retry_delay_from_error(exc: Exception) -> float | None:
    """Recursively walk Gemini's APIError details payload and return the
    `retryDelay` in seconds when the server supplies RetryInfo."""
    details = getattr(exc, "details", None)
    if not isinstance(details, (dict, list)):
        return None

    stack = [details]
    seen = set()
    while stack:
        obj = stack.pop()
        oid = id(obj)
        if oid in seen:
            continue
        seen.add(oid)

        if isinstance(obj, dict):
            # Common Google shape: details -> error -> details -> RetryInfo -> retryDelay
            if obj.get("@type") and "RetryInfo" in str(obj.get("@type")):
                parsed = _parse_retry_delay(obj.get("retryDelay"))
                if parsed is not None:
                    return parsed
            if "retryDelay" in obj:
                parsed = _parse_retry_delay(obj.get("retryDelay"))
                if parsed is not None:
                    return parsed
            if "retry_delay" in obj:
                parsed = _parse_retry_delay(obj.get("retry_delay"))
                if parsed is not None:
                    return parsed
            for val in obj.values():
                if isinstance(val, (dict, list)):
                    stack.append(val)
        elif isinstance(obj, list):
            for val in obj:
                if isinstance(val, (dict, list)):
                    stack.append(val)
    return None


def _is_gemini_resource_exhausted(exc: Exception) -> bool:
    """Detect the Gemini `429 RESOURCE_EXHAUSTED` / retryable quota error
    shape and return only a boolean, without exposing any secret value."""
    code = getattr(exc, "code", None)
    status = str(getattr(exc, "status", "") or "").upper()
    msg = str(exc).upper()
    details = getattr(exc, "details", None)

    if code == 429 or status == "RESOURCE_EXHAUSTED" or "RESOURCE_EXHAUSTED" in msg:
        if isinstance(details, dict):
            return "RESOURCE_EXHAUSTED" in str(details).upper()
        return "RESOURCE_EXHAUSTED" in msg
    return False


def _describe_one(client, entity: dict) -> str:
    facts = (entity.get("description") or "")
    meta = entity.get("metadata", {}) or {}
    facts_str = f"{facts} | metadata: {meta}"[:800] if meta else facts[:800]

    # Never fabricate a description when the source has no detail to work from.
    if not facts.strip():
        return facts

    prompt = _PROMPT.format(entity_type=entity["entity_type"], name=entity["name"], facts=facts_str)
    for attempt in range(3):
        try:
            response = client.models.generate_content(model=MODEL, contents=prompt)
            text = getattr(response, "text", "") or ""
            if not text:
                try:
                    text = response.candidates[0].content.parts[0].text
                except Exception:
                    text = ""
            return (text or facts).strip() or facts
        except APIError as exc:
            if _is_gemini_resource_exhausted(exc):
                delay = _extract_retry_delay_from_error(exc)
                if delay is not None and attempt < 2:
                    print(f"    [describe] Gemini resource exhausted; respecting retry delay {delay:.2f}s for '{entity['name']}'")
                    time.sleep(delay)
                    continue
                print(f"    [describe] Gemini resource exhausted for '{entity['name']}'; keeping original description")
                return facts
            print(f"    [describe] failed for '{entity['name']}': {exc}")
            return facts
        except Exception as exc:  # noqa: BLE001 -- any API failure should degrade, not crash the run
            print(f"    [describe] failed for '{entity['name']}': {exc}")
            return facts


def generate_descriptions(entities: list, max_workers: int = 6) -> list:
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        print("    no GEMINI_API_KEY set -- keeping original descriptions")
        return entities
    if genai is None:
        print("    google-genai not installed -- keeping original descriptions")
        return entities

    try:
        client = genai.Client(api_key=api_key)
    except Exception as exc:
        print(f"    [describe] Gemini unavailable -- keeping original descriptions ({exc})")
        return entities

    eligible = [e for e in entities if _needs_gemini_description(e)]
    if not eligible:
        print("    no entities need Gemini description generation -- keeping original descriptions")
        return entities

    # Thread count is intentionally forced low to respect the Gemini free-tier
    # limit of 5 generate_content calls per minute and avoid a burst of
    # requests for entities that already have a grounded source description.
    with ThreadPoolExecutor(max_workers=1) as pool:
        futures = {pool.submit(_describe_one, client, e): e for e in eligible}
        done = 0
        for fut in as_completed(futures):
            entity = futures[fut]
            entity["description"] = fut.result()
            done += 1
            if done % 25 == 0:
                print(f"    described {done}/{len(eligible)}...")
            time.sleep(0.02)
    return entities
