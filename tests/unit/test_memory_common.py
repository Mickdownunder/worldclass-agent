"""Unit tests for lib/memory/common.py — utcnow, hash_id, cosine_similarity."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))
import pytest
from lib.memory.common import utcnow, hash_id, cosine_similarity


def test_utcnow_returns_iso_format_string():
    """utcnow() returns a string in YYYY-MM-DDTHH:MM:SSZ format."""
    s = utcnow()
    assert isinstance(s, str)
    assert s.endswith("Z")
    assert "T" in s
    parts = s.replace("Z", "").split("T")
    assert len(parts) == 2
    date_part, time_part = parts
    assert len(date_part.split("-")) == 3
    assert len(time_part.split(":")) == 3


def test_hash_id_deterministic():
    """hash_id same input returns same 16-char hex string."""
    a = hash_id("hello")
    b = hash_id("hello")
    assert a == b
    assert len(a) == 16
    assert all(c in "0123456789abcdef" for c in a)


def test_hash_id_different_inputs_differ():
    """hash_id different inputs produce different hashes."""
    assert hash_id("a") != hash_id("b")
    assert hash_id("") != hash_id("x")


def test_hash_id_empty_string():
    """hash_id('') returns valid 16-char hex (hash of empty bytes)."""
    h = hash_id("")
    assert len(h) == 16
    assert isinstance(h, str)


def test_cosine_similarity_identical_vectors():
    """cosine_similarity([1,0,0], [1,0,0]) == 1.0."""
    a = [1.0, 0.0, 0.0]
    assert cosine_similarity(a, a) == 1.0


def test_cosine_similarity_orthogonal():
    """cosine_similarity([1,0,0], [0,1,0]) == 0.0."""
    assert cosine_similarity([1.0, 0.0, 0.0], [0.0, 1.0, 0.0]) == 0.0


def test_cosine_similarity_opposite():
    """cosine_similarity([1,0,0], [-1,0,0]) clamped to 0.0."""
    result = cosine_similarity([1.0, 0.0, 0.0], [-1.0, 0.0, 0.0])
    assert result == 0.0


def test_cosine_similarity_empty_lists_return_zero():
    """cosine_similarity([], [1,2,3]) and (a, []) return 0.0."""
    assert cosine_similarity([], [1.0, 2.0, 3.0]) == 0.0
    assert cosine_similarity([1.0, 2.0], []) == 0.0
    assert cosine_similarity([], []) == 0.0


def test_cosine_similarity_mismatched_lengths_return_zero():
    """cosine_similarity([1,2], [1,2,3]) returns 0.0."""
    assert cosine_similarity([1.0, 2.0], [1.0, 2.0, 3.0]) == 0.0


def test_cosine_similarity_non_normalized_positive():
    """cosine_similarity([2,0], [3,0]) == 1.0 (same direction)."""
    assert abs(cosine_similarity([2.0, 0.0], [3.0, 0.0]) - 1.0) < 1e-9


def test_cosine_similarity_result_in_range():
    """Result is always in [0, 1] (doc says max(0, min(1, ...)))."""
    assert 0.0 <= cosine_similarity([0.5, 0.5], [0.5, 0.5]) <= 1.0
    assert 0.0 <= cosine_similarity([1.0, 1.0], [1.0, 0.0]) <= 1.0
