"""Unit tests for tools/research_claim_outcome_schema.py (AEM contracts)."""
import json
import pytest
from pathlib import Path

from tools.research_claim_outcome_schema import (
    load_schema_for_project,
    load_global_schema,
    ensure_global_schema,
    ensure_project_schema,
    validate_authority_auditability,
    can_settle_stable,
    validate_outcome_shape,
    _default_schema_dict,
    global_schema_path,
    project_schema_path,
)


def test_default_schema_has_required_keys():
    d = _default_schema_dict()
    assert "schema_version" in d
    assert "resolution_authority_options" in d
    assert "default_claim_outcome" in d
    assert "validation_rules" in d
    assert d["default_claim_outcome"]["settlement_confidence_floor_stable"] == 0.5
    assert d["validation_rules"]["panel_or_manual_requires_audit_trace"] is True


def test_validate_authority_auditability_panel_requires_audit(schema=None):
    schema = schema or _default_schema_dict()
    # panel without audit_trace_required => violation
    errs = validate_authority_auditability(schema, {"resolution_authority": "panel", "audit_trace_required": False})
    assert len(errs) == 1
    assert "audit_trace_required" in errs[0].lower()
    # panel with audit_trace_required => ok
    errs2 = validate_authority_auditability(schema, {"resolution_authority": "panel", "audit_trace_required": True})
    assert len(errs2) == 0
    # manual method requires audit
    errs3 = validate_authority_auditability(schema, {"resolution_method": "manual", "audit_trace_required": False})
    assert len(errs3) == 1


def test_a1_invalid_resolution_authority_stable_denied():
    """A1: invalid resolution_authority or audit_trace_required missing for panel/manual => stable denied."""
    schema = _default_schema_dict()
    ok, reason = can_settle_stable(schema, {"resolution_authority": "panel", "audit_trace_required": False, "settlement_confidence": 0.9})
    assert ok is False
    assert "audit_trace_required" in reason.lower() or "panel" in reason.lower()
    errs = validate_authority_auditability(schema, {"resolution_authority": "invalid_authority"})
    assert len(errs) == 0
    errs2 = validate_outcome_shape({"outcome_type": "binary", "resolution_authority": "invalid_authority", "settlement_confidence": 0.8})
    assert any("resolution_authority" in e for e in errs2)


def test_can_settle_stable_confidence_floor():
    schema = _default_schema_dict()
    ok, reason = can_settle_stable(schema, {"settlement_confidence": 0.3, "resolution_authority": "internal_auditor"})
    assert ok is False
    assert "0.5" in reason or "PASS_STABLE" in reason
    ok2, _ = can_settle_stable(schema, {"settlement_confidence": 0.8, "resolution_authority": "internal_auditor", "audit_trace_required": False})
    assert ok2 is True


def test_can_settle_stable_evidence_type_mismatch():
    schema = _default_schema_dict()
    schema["validation_rules"]["evidence_type_mismatch_blocks_stable"] = True
    ok, reason = can_settle_stable(schema, {"settlement_confidence": 0.8}, evidence_types_used=["primary", "unknown_type"])
    assert ok is False
    assert "allowed_evidence_types" in reason or "unknown" in reason.lower()


def test_validate_outcome_shape():
    errs = validate_outcome_shape({})
    assert any("outcome_type" in e for e in errs)
    errs2 = validate_outcome_shape({"outcome_type": "binary", "settlement_confidence": 1.5})
    assert any("0" in e and "1" in e for e in errs2) or any("settlement_confidence" in e for e in errs2)
    errs3 = validate_outcome_shape({"outcome_type": "binary", "resolution_authority": "internal_auditor", "settlement_confidence": 0.7})
    assert len(errs3) == 0


def test_ensure_global_schema(mock_operator_root):
    root = mock_operator_root
    (root / "contracts").mkdir(parents=True, exist_ok=True)
    path = ensure_global_schema()
    assert path.exists()
    data = json.loads(path.read_text())
    assert data.get("schema_version") == "v1"


def test_ensure_project_schema_uses_global_if_missing(mock_operator_root, tmp_project):
    pid = tmp_project.name
    path = ensure_project_schema(pid, use_global_if_missing=True)
    # May return global path if project has no schema
    assert path.exists()
    schema = load_schema_for_project(pid)
    assert schema.get("schema_version") == "v1"


def test_load_schema_for_project_prefers_project(mock_operator_root, tmp_project):
    pid = tmp_project.name
    (tmp_project / "contracts").mkdir(parents=True, exist_ok=True)
    custom = _default_schema_dict()
    custom["schema_version"] = "v1-project"
    (tmp_project / "contracts" / "claim_outcome_schema.json").write_text(json.dumps(custom))
    schema = load_schema_for_project(pid)
    assert schema.get("schema_version") == "v1-project"
