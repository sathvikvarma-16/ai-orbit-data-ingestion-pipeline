"""Sanitization: strip HTML/entities out of text pulled from RSS/API fields."""
import re
import html


def clean_text(text: str) -> str:
    if not text:
        return ""
    text = html.unescape(text)
    text = re.sub(r"<[^>]+>", " ", text)       # strip HTML tags (common in RSS summaries)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def clean_entity(entity: dict) -> dict:
    entity["name"] = clean_text(entity.get("name", ""))
    entity["description"] = clean_text(entity.get("description", ""))
    return entity
