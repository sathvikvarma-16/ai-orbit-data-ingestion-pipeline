"""Entity resolution: canonicalize name variants (e.g. "OpenAI" vs "Open AI")
and collapse duplicates found via different sources/queries."""
import re
from urllib.parse import urlparse

_STOPWORDS = {"inc", "llc", "ltd", "corp", "corporation", "the", "labs", "co"}


def canonical_name(name: str) -> str:
    n = (name or "").lower().strip()
    n = re.sub(r"[^a-z0-9]+", " ", n)
    words = [w for w in n.split() if w not in _STOPWORDS]
    # Joined with no separator so "OpenAI" and "Open AI" canonicalize to the
    # same token -- spacing variance is exactly the kind of near-duplicate
    # this function exists to catch.
    return "".join(words)


def canonical_domain(url: str) -> str:
    if not url:
        return ""
    candidate = url if "://" in url else f"https://{url}"
    netloc = urlparse(candidate).netloc.lower()
    return netloc[4:] if netloc.startswith("www.") else netloc


def dedupe(entities: list) -> list:
    """Matches on (entity_type, canonical name) OR (entity_type, canonical domain).
    Domain matching is skipped when the domain is empty, so records with no URL
    don't all collapse into a single 'blank domain' bucket."""
    by_name = {}
    by_domain = {}
    result = []

    for e in entities:
        name_key = (e["entity_type"], canonical_name(e["name"]))
        domain = canonical_domain(e.get("url", ""))
        domain_key = (e["entity_type"], domain) if domain else None

        existing = by_name.get(name_key)
        if existing is None and domain_key is not None:
            existing = by_domain.get(domain_key)

        if existing is not None:
            if len(e.get("description", "")) > len(existing.get("description", "")):
                existing["description"] = e["description"]
            existing["categories"] = sorted(set(existing.get("categories", [])) | set(e.get("categories", [])))
            merged_meta = {**e.get("metadata", {}), **existing.get("metadata", {})}
            existing["metadata"] = merged_meta
            continue

        by_name[name_key] = e
        if domain_key is not None:
            by_domain[domain_key] = e
        result.append(e)

    return result
