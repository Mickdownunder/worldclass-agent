#!/usr/bin/env python3
"""
AEM: Claim outcome schema with authority/auditability validation.
Ensures contracts/claim_outcome_schema.json exists (project or global) and validates
per-claim outcome against resolution_authority, audit_trace_required, allowed_evidence_types.

Usage:
  research_claim_outcome_schema.py ensure <project_id>   # ensure schema exists for project
  research_claim_outcome_schema.py validate <project_id>  # validate (no-op CLI, used by other modules)

Validation rules (enforced by callers):
  1. resolution_authority=panel or resolution_method=manual => audit_trace_required must be true.
  2. settlement_confidence < 0.5 must never yield PASS_STABLE.
  3. Evidence not in allowed_evidence_types => settlement PASS_TENTATIVE or FAIL only.
  4. Missing/invalid outcome schema for a claim blocks settlement (claim stays contested/tentative).
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from tools.research_common import operator_root, project_dir, load_project, audit_log

SCHEMA_FILENAME = "claim_outcome_schema.json"
RESOLUTION_AUTHORITY_OPTIONS = {"internal_auditor", "external_source", "benchmark_suite", "panel"}
RESOLUTION_METHOD_OPTIONS = {"event", "dataset", "audit_panel", "benchmark", "manual"}
OUTCOME_TYPE_OPTIONS = {"binary", "numeric", "interval", "categorical", "ranking", "explanatory"}


def global_schema_path() -> Path:
    return operator_root() / "contracts" / SCHEMA_FILENAME


def project_schema_path(proj_path: Path) -> Path:
    return proj_path / "contracts" / SCHEMA_FILENAME


def load_global_schema() -> dict | None:
    p = global_schema_path()
    if not p.exists():
        return None
    try:
        return json.loads(p.read_text())
    except (json.JSONDecodeError, OSError):
        return None


def load_schema_for_project(project_id: str) -> dict:
    """Load schema: project-specific if present, else global default. Never returns empty dict."""
    proj_path = project_dir(project_id)
    proj_schema = proj_path / "contracts" / SCHEMA_FILENAME
    if proj_schema.exists():
        try:
            return json.loads(proj_schema.read_text())
        except (json.JSONDecodeError, OSError):
            pass
    global_schema = load_global_schema()
    if global_schema:
        return global_schema
    return _default_schema_dict()


def _default_schema_dict() -> dict:
    return {
        "schema_version": "v1",
        "resolution_authority_options": list(RESOLUTION_AUTHORITY_OPTIONS),
        "outcome_type_options": list(OUTCOME_TYPE_OPTIONS),
        "resolution_method_options": list(RESOLUTION_METHOD_OPTIONS),
        "default_claim_outcome": {
            "resolution_authority": "internal_auditor",
            "audit_trace_required": False,
            "allowed_evidence_types": ["primary", "secondary", "review", "dataset", "benchmark"],
            "oracle_failure_modes": ["ambiguous_resolution", "horizon_exceeded", "evidence_conflict", "oracle_unavailable"],
            "settlement_confidence_floor_stable": 0.5,
        },
        "validation_rules": {
            "panel_or_manual_requires_audit_trace": True,
            "settlement_confidence_stable_min": 0.5,
            "evidence_type_mismatch_blocks_stable": True,
        },
    }


def ensure_global_schema() -> Path:
    """Ensure operator/contracts/claim_outcome_schema.json exists. Returns path."""
    root = operator_root()
    contracts_dir = root / "contracts"
    contracts_dir.mkdir(parents=True, exist_ok=True)
    path = contracts_dir / SCHEMA_FILENAME
    if not path.exists():
        path.write_text(json.dumps(_default_schema_dict(), indent=2))
    return path


def ensure_project_schema(project_id: str, use_global_if_missing: bool = True) -> Path:
    """Ensure project has a usable schema (copy from global if project dir has none). Returns schema path used."""
    proj_path = project_dir(project_id)
    proj_contracts = proj_path / "contracts"
    proj_schema = proj_contracts / SCHEMA_FILENAME
    if proj_schema.exists():
        return proj_schema
    if use_global_if_missing:
        ensure_global_schema()
        # Optionally copy to project for visibility; spec says "von Tools geladen" so we can leave project empty
        return global_schema_path()
    proj_contracts.mkdir(parents=True, exist_ok=True)
    proj_schema.write_text(json.dumps(_default_schema_dict(), indent=2))
    return proj_schema


def validate_authority_auditability(schema: dict, outcome: dict) -> list[str]:
    """
    Validate authority/auditability rules. Returns list of violation messages (empty if valid).
    Rule: resolution_authority=panel or resolution_method=manual => audit_trace_required must be true.
    """
    errors = []
    rules = schema.get("validation_rules", {})
    if not rules.get("panel_or_manual_requires_audit_trace", True):
        return errors
    authority = (outcome.get("resolution_authority") or "").strip().lower()
    method = (outcome.get("resolution_method") or "").strip().lower()
    audit_required = outcome.get("audit_trace_required", False)
    if (authority == "panel" or method == "manual") and not audit_required:
        errors.append("resolution_authority=panel or resolution_method=manual requires audit_trace_required=true")
    return errors


def can_settle_stable(schema: dict, outcome: dict, evidence_types_used: list[str] | None = None) -> tuple[bool, str]:
    """
    Returns (allowed_stable, reason). PASS_STABLE only if:
    - settlement_confidence >= settlement_confidence_stable_min (default 0.5)
    - evidence_types_used all in allowed_evidence_types (if rule enabled)
    - no authority/auditability violation
    """
    rules = schema.get("validation_rules", {})
    min_conf = float(rules.get("settlement_confidence_stable_min", 0.5))
    conf = float(outcome.get("settlement_confidence", 0.0))
    if conf < min_conf:
        return False, f"settlement_confidence {conf} < {min_conf} (cannot PASS_STABLE)"
    errs = validate_authority_auditability(schema, outcome)
    if errs:
        return False, "; ".join(errs)
    if rules.get("evidence_type_mismatch_blocks_stable", True) and evidence_types_used:
        allowed = set(schema.get("default_claim_outcome", {}).get("allowed_evidence_types", []))
        for et in evidence_types_used:
            if et and et not in allowed:
                return False, f"evidence type '{et}' not in allowed_evidence_types (cannot PASS_STABLE)"
    return True, ""


def validate_outcome_shape(outcome: dict) -> list[str]:
    """Check required outcome fields exist. Returns list of error messages."""
    errors = []
    if not outcome.get("outcome_type") or str(outcome.get("outcome_type")).lower() not in OUTCOME_TYPE_OPTIONS:
        errors.append("outcome_type must be one of " + ",".join(sorted(OUTCOME_TYPE_OPTIONS)))
    if outcome.get("resolution_authority") and str(outcome["resolution_authority"]).lower() not in RESOLUTION_AUTHORITY_OPTIONS:
        errors.append("resolution_authority must be one of " + ",".join(sorted(RESOLUTION_AUTHORITY_OPTIONS)))
    if outcome.get("resolution_method") and str(outcome["resolution_method"]).lower() not in RESOLUTION_METHOD_OPTIONS:
        errors.append("resolution_method must be one of " + ",".join(sorted(RESOLUTION_METHOD_OPTIONS)))
    if "settlement_confidence" in outcome:
        sc = outcome["settlement_confidence"]
        if not isinstance(sc, (int, float)) or sc < 0 or sc > 1:
            errors.append("settlement_confidence must be float in [0, 1]")
    return errors


def main() -> None:
    if len(sys.argv) < 3:
        print("Usage: research_claim_outcome_schema.py ensure|validate <project_id>", file=sys.stderr)
        sys.exit(2)
    cmd, project_id = sys.argv[1].strip().lower(), sys.argv[2].strip()
    proj_path = project_dir(project_id)
    if not (proj_path / "project.json").exists():
        print(f"Project not found: {project_id}", file=sys.stderr)
        sys.exit(1)
    if cmd == "ensure":
        path = ensure_project_schema(project_id)
        audit_log(proj_path, "aem_claim_outcome_schema_ensure", {"schema_path": str(path)})
        print(json.dumps({"schema_path": str(path), "ok": True}))
    elif cmd == "validate":
        schema = load_schema_for_project(project_id)
        print(json.dumps({"ok": True, "schema_version": schema.get("schema_version", "v1")}))
    else:
        print("Unknown command: use ensure|validate", file=sys.stderr)
        sys.exit(2)


if __name__ == "__main__":
    main()
