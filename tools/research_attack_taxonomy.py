#!/usr/bin/env python3
"""
AEM: Weighted attack taxonomy. Generates attacks for triaged claims; writes attacks/attacks.jsonl.
Each line: attack with attack_class, attack_weight, falsification_test, minimal_repro_steps, selected_for_gate,
attack_strength, defense_strength, unresolved_residual (INTELLIGENCE_PER_TOKEN §6).

Attack classes: assumption, measurement, mechanism, external_validity, incentive_confound, temporal_drift, ontology_definition.

Usage:
  research_attack_taxonomy.py run <project_id> [--max-attacks-per-claim N]
"""
from __future__ import annotations

import json
import sys
from pathlib import Path
from datetime import datetime, timezone

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from tools.research_common import project_dir, audit_log
from tools.research_claim_triage import triage_claims

ATTACKS_DIR = "attacks"
ATTACKS_FILENAME = "attacks.jsonl"
ATTACK_CLASSES = [
    "assumption",
    "measurement",
    "mechanism",
    "external_validity",
    "incentive_confound",
    "temporal_drift",
    "ontology_definition",
]
DEFAULT_MAX_PER_CLAIM = 2
ATTACK_WEIGHT_MIN = 0.2  # Only attacks above this consume budget (plan)


def _claim_ref(c: dict) -> str:
    return f"{c.get('claim_id', '')}@{c.get('claim_version', 1)}"


def _weight_for_class(attack_class: str) -> float:
    """Default weights by class (can be overridden by config)."""
    w = {
        "assumption": 0.4,
        "measurement": 0.5,
        "mechanism": 0.5,
        "external_validity": 0.6,
        "incentive_confound": 0.5,
        "temporal_drift": 0.4,
        "ontology_definition": 0.5,
    }
    return w.get(attack_class, 0.4)


def generate_attacks_for_claim(claim: dict, attack_classes: list[str], max_per_claim: int) -> list[dict]:
    """
    Generate one attack per class (up to max_per_claim) with required fields.
    No LLM; deterministic placeholder attacks for pipeline. Real implementation can call LLM later.
    """
    ref = _claim_ref(claim)
    attacks = []
    for ac in attack_classes[:max_per_claim]:
        weight = _weight_for_class(ac)
        attacks.append({
            "claim_ref": ref,
            "claim_id": claim.get("claim_id"),
            "attack_class": ac,
            "attack_weight": weight,
            "falsification_test": f"Check {ac} for claim",
            "minimal_repro_steps": [],
            "selected_for_gate": weight >= ATTACK_WEIGHT_MIN,
            "attack_strength": weight,
            "defense_strength": 0.0,
            "unresolved_residual": 0.5,
            "ts": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        })
    return attacks


def run_attack_taxonomy(project_id: str, max_attacks_per_claim: int = DEFAULT_MAX_PER_CLAIM) -> list[dict]:
    """
    Load triaged claims, generate attacks per claim, append to attacks/attacks.jsonl. Returns all new attacks.
    """
    proj_path = project_dir(project_id)
    triaged = triage_claims(project_id, top_k=20)
    all_attacks = []
    for c in triaged:
        all_attacks.extend(generate_attacks_for_claim(c, ATTACK_CLASSES, max_attacks_per_claim))
    (proj_path / ATTACKS_DIR).mkdir(parents=True, exist_ok=True)
    path = proj_path / ATTACKS_DIR / ATTACKS_FILENAME
    existing = []
    if path.exists():
        for line in path.read_text(encoding="utf-8").strip().splitlines():
            if line.strip():
                try:
                    existing.append(json.loads(line))
                except json.JSONDecodeError:
                    continue
    # Append new attacks (dedupe by claim_ref+attack_class if desired; here we append)
    combined = existing + all_attacks
    lines = [json.dumps(a, ensure_ascii=False) for a in combined]
    path.write_text("\n".join(lines) + ("\n" if lines else ""), encoding="utf-8")
    audit_log(proj_path, "aem_attack_taxonomy_run", {"attacks_added": len(all_attacks), "total_attacks": len(combined)})
    return all_attacks


def main() -> None:
    if len(sys.argv) < 3:
        print("Usage: research_attack_taxonomy.py run <project_id> [--max-attacks-per-claim N]", file=sys.stderr)
        sys.exit(2)
    cmd, project_id = sys.argv[1].strip().lower(), sys.argv[2].strip()
    max_per = DEFAULT_MAX_PER_CLAIM
    i = 3
    while i < len(sys.argv):
        if sys.argv[i] == "--max-attacks-per-claim" and i + 1 < len(sys.argv):
            try:
                max_per = int(sys.argv[i + 1])
            except ValueError:
                pass
            i += 2
        else:
            i += 1
    proj_path = project_dir(project_id)
    if not (proj_path / "project.json").exists():
        print(f"Project not found: {project_id}", file=sys.stderr)
        sys.exit(1)
    if cmd == "run":
        attacks = run_attack_taxonomy(project_id, max_attacks_per_claim=max_per)
        print(json.dumps({"ok": True, "attacks_count": len(attacks)}))
    else:
        print("Unknown command: use run", file=sys.stderr)
        sys.exit(2)


if __name__ == "__main__":
    main()
