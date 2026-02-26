"""Shared helpers for memory modules."""
import hashlib
import time
from datetime import datetime, timezone


def utcnow() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def hash_id(text: str) -> str:
    return hashlib.sha256(text.encode()).hexdigest()[:16]
