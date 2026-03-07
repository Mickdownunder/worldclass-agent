"""Unit tests for tools/research_memory_policy.py."""
import pytest

from tools.research_memory_policy import decide, reason, THRESHOLDS


def test_decide_accepted():
    """decide() returns accepted when above thresholds."""
    f = {"reliability_score": 0.7, "importance_score": 0.6, "verification_status": "confirmed"}
    assert decide(f) == "accepted"


def test_decide_quarantined_low_importance():
    """decide() returns quarantined when importance below min."""
    f = {"reliability_score": 0.8, "importance_score": 0.3, "verification_status": "confirmed"}
    assert decide(f) == "quarantined"


def test_decide_rejected_unverified():
    """decide() returns rejected when verification_status is unverified."""
    f = {"reliability_score": 0.9, "importance_score": 0.9, "verification_status": "unverified"}
    assert decide(f) == "rejected"


def test_decide_rejected_low_reliability():
    """decide() returns rejected when reliability < 0.3."""
    f = {"reliability_score": 0.2, "importance_score": 0.8}
    assert decide(f) == "rejected"


def test_reason_accepted():
    """reason() for accepted is descriptive."""
    assert "reliability" in reason({}, "accepted").lower() or "passed" in reason({}, "accepted").lower()


def test_reason_rejected_unverified():
    """reason() for rejected with verification_status=unverified."""
    r = reason({"verification_status": "unverified"}, "rejected")
    assert "unverified" in r.lower()


def test_reason_rejected_low_reliability():
    """reason() for rejected due to reliability below 0.3."""
    r = reason({"reliability_score": 0.2, "importance_score": 0.5}, "rejected")
    assert "reliability" in r.lower() or "threshold" in r.lower()


def test_reason_rejected_other():
    """reason() for rejected for other reasons (failed minimum thresholds)."""
    r = reason({"reliability_score": 0.5, "importance_score": 0.4}, "rejected")
    assert "threshold" in r.lower() or "minimum" in r.lower()


def test_reason_quarantined():
    """reason() for quarantined."""
    r = reason({"reliability_score": 0.7, "importance_score": 0.3}, "quarantined")
    assert "quarantined" in r.lower() or "threshold" in r.lower()


def test_thresholds_defined():
    """THRESHOLDS dict is defined."""
    assert THRESHOLDS["reliability_min"] >= 0
    assert THRESHOLDS["importance_min"] >= 0
    assert "verification_reject" in THRESHOLDS
