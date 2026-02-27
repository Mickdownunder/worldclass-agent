#!/usr/bin/env python3
"""
AEM: Reopen protocol. Triggers: contradiction delta, decay threshold, shock-event, ontology drift.
Action: set affected claims to contested; optionally spawn evidence acquisition (handled by workflow).
"""
from __future__ import annotations

import json
import sys
from pathlib import Path
from datetime import datetime, timezone

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from tools.research_common import project_dir, load_project, audit_log
from tools.research_claim_state_machine import load_ledger_jsonl, save_ledger_jsonl, apply_transition

REOPEN_TRIGGERS = ["contradiction_delta", "decay_threshold", "shock_event", "ontology_drift"]


def check_reopen_triggers(project_id: str) -> list[dict]:
    """
    Check ledger for reopen conditions. Returns list of { trigger, claim_ref, detail }.
    Does not modify state; caller can apply_transition to contested.
    """
    proj_path = project_dir(project_id)
    claims = load_ledger_jsonl(proj_path)
    project = load_project(proj_path)
    triggers = []
    for c in claims:
        ref = f"{c.get('claim_id', '')}@{c.get('claim_version', 1)}"
        if (c.get("contradicts") or []) and (c.get("state") or "").lower() == "stable":
            triggers.append({"trigger": "contradiction_delta", "claim_ref": ref, "detail": "contradiction_link_present"})
        if c.get("tentative_cycles_used", 0) >= 3 and (c.get("state") or "").lower() not in ("retired", "falsified"):
            triggers.append({"trigger": "decay_threshold", "claim_ref": ref, "detail": "tentative_cycles_high"})
    return triggers


def apply_reopen(project_id: str, trigger_list: list[dict] | None = None) -> int:
    """Set affected claims to contested. If trigger_list None, run check_reopen_triggers first. Returns count updated."""
    if trigger_list is None:
        trigger_list = check_reopen_triggers(project_id)
    count = 0
    for t in trigger_list:
        ref = t.get("claim_ref")
        if not ref:
            continue
        try:
            apply_transition(project_id, ref, "contested")
            count += 1
        except ValueError:
            pass
    proj_path = project_dir(project_id)
    if count:
        audit_log(proj_path, "aem_reopen_applied", {"count": count, "triggers": [x.get("trigger") for x in trigger_list]})
    return count


def main() -> None:
    if len(sys.argv) < 3:
        print("Usage: research_reopen_protocol.py check|apply <project_id>", file=sys.stderr)
        sys.exit(2)
    cmd, project_id = sys.argv[1].strip().lower(), sys.argv[2].strip()
    proj_path = project_dir(project_id)
    if not (proj_path / "project.json").exists():
        print(f"Project not found: {project_id}", file=sys.stderr)
        sys.exit(1)
    if cmd == "check":
        out = check_reopen_triggers(project_id)
        print(json.dumps({"triggers": out}))
    elif cmd == "apply":
        n = apply_reopen(project_id)
        print(json.dumps({"ok": True, "claims_set_contested": n}))
    else:
        print("Unknown command: use check|apply", file=sys.stderr)
        sys.exit(2)


if __name__ == "__main__":
    main()
