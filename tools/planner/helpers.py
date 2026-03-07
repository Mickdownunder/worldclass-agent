"""Shared helpers: JSON parse, slug, medical detection, entity extraction, priority."""
import json
import re
from typing import Any

from tools.planner.constants import TOPIC_STOPWORDS, PRIORITY_MAP, get_medical_keywords, get_non_clinical_markers


def json_only(text: str) -> dict[str, Any]:
    t = (text or "").strip()
    if t.startswith("```"):
        parts = t.split("```")
        if len(parts) >= 2:
            t = parts[1].replace("json", "", 1).strip()
    return json.loads(t)


def slug(s: str, fallback: str) -> str:
    out = re.sub(r"[^a-z0-9]+", "-", s.lower()).strip("-")
    return out or fallback


def is_medical_topic(text: str) -> bool:
    text_lower = text.lower()
    non_clinical = sum(1 for kw in get_non_clinical_markers() if kw in text_lower)
    if non_clinical >= 2:
        return False
    matches = sum(1 for kw in get_medical_keywords() if kw in text_lower)
    return matches >= 3


def extract_entities(question: str) -> list[str]:
    seen: set[str] = set()
    entities: list[str] = []
    pattern = r"\b([A-Z][A-Za-z0-9\-\+]{2,}(?:\s+[A-Z][A-Za-z0-9\-\+]{2,}){0,3})\b"
    for m in re.finditer(pattern, question):
        cand = m.group(1).strip()
        if len(cand) < 3:
            continue
        key = cand.lower()
        if key in seen:
            continue
        words = key.split()
        if all(w in TOPIC_STOPWORDS for w in words):
            continue
        seen.add(key)
        entities.append(cand)
    return entities[:20]


def parse_priority(val: Any) -> int:
    if isinstance(val, int):
        return max(1, min(3, val))
    s = str(val).strip().lower()
    if s in PRIORITY_MAP:
        return PRIORITY_MAP[s]
    try:
        return max(1, min(3, int(s)))
    except (ValueError, TypeError):
        return 2
