"""
Integration check: Audit API/UI data must match claim_ledger / claim_evidence_map.
Run from repo root: python3 tests/research/test_audit_consistency.py
"""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT))


def get_audit_from_files(project_id: str) -> dict | None:
    """Replicate getAudit() logic (ui/src/lib/operator/research.ts) for consistency check."""
    proj_path = ROOT / "research" / project_id
    if not proj_path.is_dir():
        return None
    verify_dir = proj_path / "verify"
    try:
        evidence_path = verify_dir / "claim_evidence_map_latest.json"
        ledger_path = verify_dir / "claim_ledger.json"
        raw = None
        source = None
        try:
            raw = evidence_path.read_text()
            source = "claim_evidence_map_latest"
        except FileNotFoundError:
            raw = ledger_path.read_text()
            source = "claim_ledger"
        data = json.loads(raw)
        claims_raw = data.get("claims", [])
        claims = []
        for c in claims_raw:
            claims.append({
                "claim_id": str(c.get("claim_id", "")),
                "text": (c.get("text") or "")[:500],
                "is_verified": bool(c.get("is_verified")),
                "verification_reason": str(c["verification_reason"]) if c.get("verification_reason") is not None else None,
                "supporting_source_ids": c.get("supporting_source_ids", []) if isinstance(c.get("supporting_source_ids"), list) else [],
            })
        return {"claims": claims, "source": source}
    except Exception:
        return None


def test_audit_consistency():
    """Audit data from files must have correct verified/unverified structure."""
    # Use E2E fixture: 2 verified, 1 unverified
    audit = get_audit_from_files("proj-e2e-check")
    assert audit is not None, "proj-e2e-check should have verify/claim_ledger.json"
    claims = audit["claims"]
    assert len(claims) == 3, f"Expected 3 claims, got {len(claims)}"
    verified = [c for c in claims if c["is_verified"]]
    unverified = [c for c in claims if not c["is_verified"]]
    assert len(verified) == 2, f"Expected 2 verified, got {len(verified)}"
    assert len(unverified) == 1, f"Expected 1 unverified, got {len(unverified)}"
    for c in claims:
        assert "claim_id" in c and "text" in c and "is_verified" in c
        assert "supporting_source_ids" in c and isinstance(c["supporting_source_ids"], list)
    # Verify unverified has verification_reason
    assert any(c.get("verification_reason") for c in unverified)
    print("Audit consistency OK: verified=2, unverified=1, structure matches claim_ledger.")


if __name__ == "__main__":
    test_audit_consistency()
    print("Check 3 (Audit) passed.")
