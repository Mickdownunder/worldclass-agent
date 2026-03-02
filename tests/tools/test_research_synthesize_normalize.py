"""
Regression tests: nested source_finding_ids / supporting_source_ids must never crash.
Discovery fail hardening: normalize_to_strings and helpers used in _build_provenance_appendix,
_build_claim_source_registry must handle lists, nested lists, dicts, mixed types.
"""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from tools.research_synthesize import (
    normalize_to_strings,
    _build_provenance_appendix,
    _build_claim_source_registry,
)


def test_normalize_to_strings_empty_and_none():
    assert normalize_to_strings(None) == []
    assert normalize_to_strings([]) == []


def test_normalize_to_strings_flat_list():
    assert normalize_to_strings(["a", "b", "c"]) == ["a", "b", "c"]


def test_normalize_to_strings_nested_list():
    # sequence item expected str instance, list found — must not crash
    assert normalize_to_strings(["a", ["b", "c"], "d"]) == ["a", "b", "c", "d"]


def test_normalize_to_strings_deeply_nested():
    assert normalize_to_strings([["x"], [["y"], "z"]]) == ["x", "y", "z"]


def test_normalize_to_strings_mixed_with_dict():
    # dicts are stringified (compact json or str)
    out = normalize_to_strings(["url1", {"nested": 1}, "url2"])
    assert len(out) == 3
    assert out[0] == "url1"
    assert out[2] == "url2"
    assert "nested" in out[1] or "1" in out[1]


def test_normalize_to_strings_scalar():
    assert normalize_to_strings("only") == ["only"]


def test_build_provenance_appendix_nested_source_finding_ids():
    ledger = [
        {"claim_id": "c1", "source_finding_ids": ["f1", "f2"]},
        {"claim_id": "c2", "source_finding_ids": ["f3", ["f4", "f5"]]},  # nested list
        {"claim_id": "c3", "source_finding_ids": None},
    ]
    md = _build_provenance_appendix(ledger)
    assert "| c1 |" in md
    assert "| c2 |" in md
    assert "| c3 |" in md
    assert "f1" in md and "f2" in md
    assert "f3" in md and "f4" in md and "f5" in md


def test_build_claim_source_registry_nested_supporting_source_ids():
    ledger = [
        {"text": "Claim A", "supporting_source_ids": ["https://a.com"]},
        {"text": "Claim B", "supporting_source_ids": ["https://b.com", ["https://c.com"]]},
    ]
    sources = [
        {"url": "https://a.com", "published_date": "2024-01-01"},
        {"url": "https://b.com"},
        {"url": "https://c.com"},
    ]
    ref_list = [("https://a.com", "A"), ("https://b.com", "B"), ("https://c.com", "C")]
    md = _build_claim_source_registry(ledger, sources, ref_list)
    assert "Claim A" in md or "Claim" in md
    assert "| # |" in md
