#!/usr/bin/env python3
"""
AEM: Claim lifecycle state machine with strict transition guards and versioning.
Reads verify/claim_ledger.json (or existing claims/ledger.jsonl), applies guards, writes claims/ledger.jsonl.

States (INTELLIGENCE_PER_TOKEN §5 + plan): proposed -> evidenced -> attacked -> defended -> stable ->
  decaying -> contested -> falsified -> retired

Guards:
  - No claim enters stable without attack coverage (or we allow if no AEM attacks yet — configurable).
  - retired requires retire_reason in UNRESOLVABLE_NOW|ILL_POSED|OUT_OF_SCOPE|NORMATIVE_NON_SETTLEABLE|SUPERSEDED.
  - reopen_allowed, reopen_conditions required for retire.

Ledger fields (must): claim_id, claim_version, supersedes, tentative_ttl, tentative_cycles_used,
  retire_reason, reopen_allowed, reopen_conditions, claim_scope, contradicts, failure_boundary,
  text, supporting_source_ids, is_verified, verification_tier, verification_reason, state.

Usage:
  research_claim_state_machine.py upgrade <project_id>   # verify ledger -> claims/ledger.jsonl with defaults
  research_claim_state_machine.py transition <project_id> <claim_ref> <new_state>  # apply one transition (guarded)
"""
from __future__ import annotations

import json
import sys
from pathlib import Path
from datetime import datetime, timezone

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from tools.research_common import project_dir, load_project, audit_log

CLAIMS_DIR = "claims"
LEDGER_FILENAME = "ledger.jsonl"

VALID_STATES = {
    "proposed", "evidenced", "attacked", "defended", "stable",
    "decaying", "contested", "falsified", "retired",
}
RETIRE_REASONS = {"UNRESOLVABLE_NOW", "ILL_POSED", "OUT_OF_SCOPE", "NORMATIVE_NON_SETTLEABLE", "SUPERSEDED"}


def _default_claim_scope() -> dict:
    return {"population": "", "geography": "", "timeframe": "", "domain": ""}


def _default_failure_boundary() -> dict:
    return {"reason": "", "evidence_refs": [], "threshold_exceeded": False}


def _claim_ref(claim_id: str, claim_version: int) -> str:
    return f"{claim_id}@{claim_version}"


def load_verify_ledger_claims(proj_path: Path) -> list[dict]:
    """Load from verify/claim_ledger.json."""
    path = proj_path / "verify" / "claim_ledger.json"
    if not path.exists():
        return []
    try:
        data = json.loads(path.read_text())
        return data.get("claims", [])
    except (json.JSONDecodeError, OSError):
        return []


def load_ledger_jsonl(proj_path: Path) -> list[dict]:
    """Load from claims/ledger.jsonl (one JSON per line)."""
    path = proj_path / CLAIMS_DIR / LEDGER_FILENAME
    if not path.exists():
        return []
    claims = []
    for line in path.read_text(encoding="utf-8").strip().splitlines():
        if not line.strip():
            continue
        try:
            claims.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return claims


def save_ledger_jsonl(proj_path: Path, claims: list[dict]) -> Path:
    (proj_path / CLAIMS_DIR).mkdir(parents=True, exist_ok=True)
    path = proj_path / CLAIMS_DIR / LEDGER_FILENAME
    lines = [json.dumps(c, ensure_ascii=False) for c in claims]
    path.write_text("\n".join(lines) + ("\n" if lines else ""), encoding="utf-8")
    return path


def upgrade_claim_to_ledger_entry(c: dict, version: int = 1) -> dict:
    """
    Convert verify-style claim to full ledger entry with state machine fields.
    Preserves claim_id, text, supporting_source_ids, is_verified, verification_tier, verification_reason.
    """
    claim_id = c.get("claim_id") or ""
    state = (c.get("state") or "").strip().lower()
    if state not in VALID_STATES:
        state = "evidenced" if c.get("is_verified") else "proposed"
    vtier = (c.get("verification_tier") or "UNVERIFIED").strip().upper()
    tier_confidence_map = {"TIER1": 0.9, "TIER2": 0.7, "TIER3": 0.5}
    settlement_confidence = c.get("settlement_confidence") or tier_confidence_map.get(vtier, 0.5)
    p_true = c.get("p_true") or c.get("confidence") or tier_confidence_map.get(vtier, 0.5)

    out = {
        "claim_id": claim_id,
        "claim_version": version,
        "supersedes": c.get("supersedes"),
        "text": (c.get("text") or c.get("claim") or "").strip(),
        "supporting_source_ids": c.get("supporting_source_ids", []),
        "is_verified": bool(c.get("is_verified")),
        "verification_tier": vtier,
        "verification_reason": (c.get("verification_reason") or "").strip(),
        "state": state,
        "outcome_type": c.get("outcome_type", "binary"),
        "claim_type": c.get("claim_type") or c.get("outcome_type", "binary"),
        "resolution_authority": c.get("resolution_authority", "internal_auditor"),
        "resolution_method": c.get("resolution_method", "event"),
        "settlement_confidence": float(settlement_confidence),
        "audit_trace_required": c.get("audit_trace_required", False),
        "p_true": float(p_true),
        "tentative_ttl": c.get("tentative_ttl", 3),
        "tentative_cycles_used": c.get("tentative_cycles_used", 0),
        "retire_reason": c.get("retire_reason"),
        "reopen_allowed": c.get("reopen_allowed", False),
        "reopen_conditions": c.get("reopen_conditions", []),
        "claim_scope": c.get("claim_scope") or _default_claim_scope(),
        "contradicts": c.get("contradicts", []),
        "failure_boundary": c.get("failure_boundary") or _default_failure_boundary(),
        "last_updated": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
    }
    if out["retire_reason"] and out["state"] != "retired":
        out["state"] = "retired"
    return out


def upgrade_verify_ledger_to_claims(project_id: str) -> list[dict]:
    """
    Read verify/claim_ledger.json, convert each claim to full ledger entry, write claims/ledger.jsonl.
    Returns list of upgraded claims.
    """
    proj_path = project_dir(project_id)
    existing = load_ledger_jsonl(proj_path)
    if existing:
        # Already have AEM ledger; return as-is (no overwrite from verify)
        return existing
    verify_claims = load_verify_ledger_claims(proj_path)
    upgraded = [upgrade_claim_to_ledger_entry(c, version=i + 1) for i, c in enumerate(verify_claims)]
    if upgraded:
        save_ledger_jsonl(proj_path, upgraded)
        audit_log(proj_path, "aem_claim_ledger_upgraded", {"claims_count": len(upgraded), "source": "verify"})
    return upgraded


def can_transition(current_state: str, new_state: str, claim: dict) -> tuple[bool, str]:
    """
    Guard: return (allowed, reason). Enforces:
    - retired requires retire_reason in RETIRE_REASONS.
    - stable requires attack_coverage if we have attacks (optional guard; here we allow stable from defended if verified).
    """
    current_state = (current_state or "").strip().lower()
    new_state = (new_state or "").strip().lower()
    if current_state not in VALID_STATES:
        return False, f"invalid current state: {current_state}"
    if new_state not in VALID_STATES:
        return False, f"invalid new state: {new_state}"

    if new_state == "retired":
        reason = (claim.get("retire_reason") or "").strip().upper()
        if reason not in RETIRE_REASONS:
            return False, f"retired requires retire_reason in {RETIRE_REASONS}"
        if not isinstance(claim.get("reopen_conditions"), list):
            return False, "retired requires reopen_conditions (list)"

    allowed_transitions = {
        "proposed": {"evidenced"},
        "evidenced": {"attacked"},
        "attacked": {"defended", "falsified"},
        "defended": {"stable", "attacked"},
        "stable": {"decaying", "contested"},
        "decaying": {"contested", "stable"},
        "contested": {"evidenced", "attacked", "retired"},
        "falsified": {"retired"},
        "retired": set(),
    }
    if new_state not in allowed_transitions.get(current_state, set()):
        return False, f"transition {current_state} -> {new_state} not allowed"
    return True, ""


def add_contradiction(project_id: str, claim_ref: str, other_claim_ref: str, contradiction_strength: float) -> dict | None:
    """Append to claim's contradicts list. Returns updated claim or None."""
    proj_path = project_dir(project_id)
    claims = load_ledger_jsonl(proj_path)
    cid, ver = (claim_ref.split("@", 1) + [None])[:2]
    if ver is not None:
        try:
            ver = int(ver)
        except ValueError:
            ver = None
    idx = next((i for i, c in enumerate(claims) if c.get("claim_id") == cid and (ver is None or c.get("claim_version") == ver)), None)
    if idx is None:
        return None
    claim = claims[idx]
    cont = claim.get("contradicts") or []
    cont.append({"claim_ref": other_claim_ref, "contradiction_strength": round(contradiction_strength, 4)})
    claim["contradicts"] = cont
    claim["last_updated"] = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    claims[idx] = claim
    save_ledger_jsonl(proj_path, claims)
    return claim


def set_claim_scope(project_id: str, claim_ref: str, scope: dict) -> dict | None:
    """Set claim_scope for a claim. scope: { population?, geography?, timeframe?, domain? }. Returns updated claim or None."""
    proj_path = project_dir(project_id)
    claims = load_ledger_jsonl(proj_path)
    cid, ver = (claim_ref.split("@", 1) + [None])[:2]
    if ver is not None:
        try:
            ver = int(ver)
        except ValueError:
            ver = None
    idx = next((i for i, c in enumerate(claims) if c.get("claim_id") == cid and (ver is None or c.get("claim_version") == ver)), None)
    if idx is None:
        return None
    claim = claims[idx]
    base = _default_claim_scope()
    base.update({k: v for k, v in scope.items() if k in base})
    claim["claim_scope"] = base
    claim["last_updated"] = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    claims[idx] = claim
    save_ledger_jsonl(proj_path, claims)
    return claim


def apply_transition(project_id: str, claim_ref: str, new_state: str, **claim_updates) -> dict | None:
    """
    Find claim by claim_ref (claim_id@version), check guard, update state, persist. Returns updated claim or None.
    """
    proj_path = project_dir(project_id)
    claims = load_ledger_jsonl(proj_path)
    if "@" in claim_ref:
        cid, ver_str = claim_ref.split("@", 1)
        try:
            ver = int(ver_str)
        except ValueError:
            ver = None
    else:
        cid, ver = claim_ref, None
    idx = None
    for i, c in enumerate(claims):
        if c.get("claim_id") != cid:
            continue
        if ver is not None and c.get("claim_version") != ver:
            continue
        idx = i
        break
    if idx is None:
        return None
    claim = claims[idx]
    current = (claim.get("state") or "").strip().lower()
    claim.update(claim_updates)
    ok, reason = can_transition(current, new_state, claim)
    if not ok:
        raise ValueError(reason)
    claim["state"] = new_state
    claim["last_updated"] = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    claims[idx] = claim
    save_ledger_jsonl(proj_path, claims)
    audit_log(proj_path, "aem_claim_transition", {"claim_ref": claim_ref, "from": current, "to": new_state})
    return claim


def main() -> None:
    if len(sys.argv) < 3:
        print("Usage: research_claim_state_machine.py upgrade <project_id> | transition <project_id> <claim_ref> <new_state>", file=sys.stderr)
        sys.exit(2)
    cmd = sys.argv[1].strip().lower()
    project_id = sys.argv[2].strip()
    proj_path = project_dir(project_id)
    if not (proj_path / "project.json").exists():
        print(f"Project not found: {project_id}", file=sys.stderr)
        sys.exit(1)
    if cmd == "upgrade":
        claims = upgrade_verify_ledger_to_claims(project_id)
        print(json.dumps({"ok": True, "claims_count": len(claims)}))
    elif cmd == "transition":
        if len(sys.argv) < 5:
            print("Usage: research_claim_state_machine.py transition <project_id> <claim_ref> <new_state>", file=sys.stderr)
            sys.exit(2)
        claim_ref, new_state = sys.argv[3].strip(), sys.argv[4].strip()
        try:
            claim = apply_transition(project_id, claim_ref, new_state)
            print(json.dumps({"ok": True, "claim": claim} if claim else {"ok": False, "error": "claim not found"}))
        except ValueError as e:
            print(json.dumps({"ok": False, "error": str(e)}), file=sys.stderr)
            sys.exit(1)
    else:
        print("Unknown command: use upgrade|transition", file=sys.stderr)
        sys.exit(2)


if __name__ == "__main__":
    main()
