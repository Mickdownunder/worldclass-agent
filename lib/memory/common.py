"""Shared helpers for memory modules."""
import hashlib
import time
from datetime import datetime, timezone


def utcnow() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def hash_id(text: str) -> str:
    return hashlib.sha256(text.encode()).hexdigest()[:16]


def cosine_similarity(a: list[float], b: list[float]) -> float:
    """Cosine similarity between two vectors. Returns 0 if invalid."""
    if not a or not b or len(a) != len(b):
        return 0.0
    try:
        dot = sum(x * y for x, y in zip(a, b))
        na = sum(x * x for x in a) ** 0.5
        nb = sum(y * y for y in b) ** 0.5
        if na <= 0 or nb <= 0:
            return 0.0
        return max(0.0, min(1.0, dot / (na * nb)))
    except (TypeError, ValueError):
        return 0.0
