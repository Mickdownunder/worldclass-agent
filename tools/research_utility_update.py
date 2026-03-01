#!/usr/bin/env python3
"""
Update memory utilities from project outcome: mark which retrieved principles/findings
were helpful (critic_score >= 0.7). Reads prior_knowledge.json and project.json.
Usage: research_utility_update.py <project_id>
"""
import json
import sys
from pathlib import Path
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))


def main() -> None:
    if len(sys.argv) < 2:
        sys.exit(0)
    project_id = sys.argv[1].strip()
    proj_dir = ROOT / "research" / project_id
    if not proj_dir.is_dir():
        sys.exit(0)
    prior_path = proj_dir / "prior_knowledge.json"
    principle_ids = []
    finding_ids = []
    try:
        if prior_path.exists():
            prior = json.loads(prior_path.read_text())
            principle_ids = prior.get("principle_ids") or []
            finding_ids = [str(x) for x in prior.get("finding_ids") or []]
    except Exception:
        principle_ids = []
        finding_ids = []
    project_json = proj_dir / "project.json"
    critic_score = 0.5
    question = ""
    if project_json.exists():
        try:
            d = json.loads(project_json.read_text())
            question = str(d.get("question") or "")
            c = d.get("quality_gate", {}).get("critic_score")
            if c is not None:
                critic_score = float(c)
        except Exception:
            pass
    strategy_profile_id = None
    strategy_path = proj_dir / "memory_strategy.json"
    if strategy_path.exists():
        try:
            ms = json.loads(strategy_path.read_text())
            selected = ms.get("selected_strategy") if isinstance(ms.get("selected_strategy"), dict) else {}
            strategy_profile_id = selected.get("id")
        except Exception:
            strategy_profile_id = None
    try:
        from lib.memory import Memory
        mem = Memory()
        if principle_ids:
            mem.update_utilities_from_outcome("principle", principle_ids, critic_score, context_key=question or None)
        if finding_ids:
            mem.update_utilities_from_outcome("finding", finding_ids, critic_score, context_key=question or None)

        # Memory v2: strategy reinforcement from verified outcomes.
        if project_json.exists() and strategy_profile_id:
            try:
                d = json.loads(project_json.read_text())
            except Exception:
                d = {}
            qg = d.get("quality_gate", {}) if isinstance(d.get("quality_gate"), dict) else {}
            eg = qg.get("evidence_gate", {}) if isinstance(qg.get("evidence_gate"), dict) else {}
            metrics = eg.get("metrics", {}) if isinstance(eg.get("metrics"), dict) else {}
            status = str(d.get("status") or "")
            evidence_gate_pass = str(eg.get("status") or "").lower() == "passed"
            critic_pass = float(qg.get("critic_score") or 0.0) >= 0.55
            user_verdict = "approved" if status == "done" else "rejected" if status.startswith("failed") else "none"
            claim_support_rate = metrics.get("claim_support_rate")
            if not isinstance(claim_support_rate, (int, float)):
                claim_support_rate = None
            mem.update_strategy_from_outcome(
                strategy_profile_id=strategy_profile_id,
                critic_pass=critic_pass,
                evidence_gate_pass=evidence_gate_pass,
                user_verdict=user_verdict,
                claim_support_rate=claim_support_rate,
                failed_quality_gate=status == "failed_quality_gate",
            )
            mem.record_memory_decision(
                decision_type="strategy_outcome_update",
                details={
                    "strategy_profile_id": strategy_profile_id,
                    "status": status,
                    "critic_pass": critic_pass,
                    "evidence_gate_pass": evidence_gate_pass,
                    "claim_support_rate": claim_support_rate,
                },
                project_id=project_id,
                phase="post_run",
                strategy_profile_id=strategy_profile_id,
                confidence=0.7,
            )

        # Memory v2: provenance/source domain stats.
        try:
            d = json.loads(project_json.read_text()) if project_json.exists() else {}
            topic_domain = str(d.get("domain") or "general")
            verified_urls = set()
            ledger_path = proj_dir / "verify" / "claim_ledger.json"
            if ledger_path.exists():
                ledger = json.loads(ledger_path.read_text())
                claims = ledger.get("claims", []) if isinstance(ledger, dict) else []
                for c in claims:
                    if c.get("is_verified"):
                        for u in (c.get("supporting_source_ids") or []):
                            verified_urls.add(str(u).strip())
            for sf in (proj_dir / "sources").glob("*.json"):
                if sf.name.endswith("_content.json"):
                    continue
                try:
                    sd = json.loads(sf.read_text())
                except Exception:
                    continue
                url = (sd.get("url") or "").strip()
                domain = urlparse(url).netloc.replace("www.", "") if url else ""
                if not domain:
                    continue
                rel = sd.get("relevance_score")
                rel_hit = 1 if isinstance(rel, (int, float)) and rel >= 8 else 0
                ver_hit = 1 if url in verified_urls else 0
                fail_hit = 1 if isinstance(rel, (int, float)) and rel < 5 else 0
                mem.update_source_domain_stats_v2(
                    domain=domain,
                    topic_domain=topic_domain,
                    times_seen=1,
                    verified_hits=ver_hit,
                    relevant_hits=rel_hit,
                    fail_hits=fail_hit,
                )
        except Exception:
            pass
        mem.close()
    except Exception as e:
        print(f"[utility_update] failed (non-fatal): {e}", file=sys.stderr)
    sys.exit(0)


if __name__ == "__main__":
    main()
