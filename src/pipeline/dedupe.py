"""Entity resolution: canonicalize name variants (e.g. "OpenAI" vs "Open AI")
and collapse duplicates found via different sources/queries while remaining conservative.
"""
import re
from urllib.parse import urlparse

_STOPWORDS = {"inc", "llc", "ltd", "corp", "corporation", "the", "labs", "co", "company", "foundation"}
_LEGAL_SUFFIXES = {"inc", "incorporated", "llc", "ltd", "corp", "corporation", "plc"}


def canonical_name(name: str) -> str:
    n = (name or "").lower().strip()
    # Keep the letter+digit boundary intact where possible, but normalize
    # spacing and punctuation across the exact same entity family.
    n = re.sub(r"[\-_/\"]+", " ", n)
    n = re.sub(r"[^a-z0-9]+", " ", n)
    # Remove legal suffix tokens only if they occur at the end of the company-like phrase.
    raw_words = [w for w in n.split() if w]
    if raw_words:
        while raw_words and raw_words[-1] in _LEGAL_SUFFIXES:
            raw_words.pop()
    words = [w for w in raw_words if w not in _STOPWORDS]
    # Join so spacing variants collapse to the same canonical digest.
    return "".join(words)


def canonical_domain(url: str) -> str:
    if not url:
        return ""
    candidate = url if "://" in url else f"https://{url}"
    netloc = urlparse(candidate).netloc.lower().strip()
    if netloc.startswith("www."):
        netloc = netloc[4:]
    # Strip common port noise and any trailing slash-like host artifacts.
    netloc = netloc.split(":", 1)[0].strip()
    return netloc


def dedupe(entities: list) -> list:
    """Matches on (entity_type, canonical name) OR (entity_type, canonical domain).
    Domain matching is skipped when the domain is empty, so records with no URL
    don't collapse into a single blank-domain bucket.
    """
    by_name = {}
    by_domain = {}
    result = []

    for e in entities:
        entity_type = (e.get("entity_type") or "").strip().lower()
        name_key = (entity_type, canonical_name(e.get("name", "")))
        domain = canonical_domain(e.get("url", ""))
        domain_key = (entity_type, domain) if domain else None

        existing = by_name.get(name_key)
        if existing is None and domain_key is not None:
            existing = by_domain.get(domain_key)

        if existing is not None:
            # Merge only when the same canonical entity is found. Keep the richer
            # description, union of categories, and metadata union.
            if len((e.get("description") or "")) > len((existing.get("description") or "")):
                existing["description"] = e.get("description", "")
            existing["categories"] = sorted(set(existing.get("categories", [])) | set(e.get("categories", [])))
            merged_meta = {**existing.get("metadata", {}), **e.get("metadata", {})}
            existing["metadata"] = merged_meta
            continue

        by_name[name_key] = e
        if domain_key is not None:
            by_domain[domain_key] = e
        result.append(e)

    return result
