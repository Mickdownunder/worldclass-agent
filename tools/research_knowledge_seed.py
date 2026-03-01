#!/usr/bin/env python3
"""
Knowledge Seeder: seed new projects with utility-ranked prior findings and principles.
Writes prior_knowledge.json to project dir for explore phase to use.
Usage: research_knowledge_seed.py <project_id>
"""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))


def main() -> None:
    if len(sys.argv) < 2:
        print("Usage: research_knowledge_seed.py <project_id>", file=sys.stderr)
        sys.exit(2)
    project_id = sys.argv[1].strip()
    proj_dir = ROOT / "research" / project_id
    if not proj_dir.is_dir():
        print(f"Project dir not found: {proj_dir}", file=sys.stderr)
        sys.exit(1)
    project_json = proj_dir / "project.json"
    if not project_json.exists():
        sys.exit(0)
    d = json.loads(project_json.read_text())
    question = (d.get("question") or "").strip()
    if not question:
        sys.exit(0)
    try:
        from lib.memory import Memory
        mem = Memory()
        principles = mem.retrieve_with_utility(question, "principle", k=5, context_key=question)
        findings = mem.retrieve_with_utility(question, "finding", k=10, context_key=question)
        
        lateral_principles = []
        research_mode = d.get("config", {}).get("research_mode", "standard")
        if research_mode == "discovery":
            try:
                top_utils = mem.get_top_utility(memory_type="principle", limit=15)
                # Filter out ones already in principles
                existing_ids = {p.get("id") for p in principles if p.get("id")}
                for tu in top_utils:
                    pid = tu.get("memory_id")
                    if pid and pid not in existing_ids:
                        row = mem._conn.execute("SELECT * FROM strategic_principles WHERE id = ?", (pid,)).fetchone()
                        if row:
                            lateral_principles.append(dict(row))
                        if len(lateral_principles) >= 3:
                            break
            except Exception as le:
                print(f"Lateral inspiration failed: {le}", file=sys.stderr)

        principle_ids = [p["id"] for p in principles if p.get("id")]
        finding_ids = [str(f["id"]) for f in findings if f.get("id")]
        mem.record_memory_decision(
            decision_type="knowledge_seed_retrieval",
            details={
                "question": question[:240],
                "retrieved_memory_ids": {
                    "principle_ids": principle_ids,
                    "finding_ids": finding_ids,
                },
                "counts": {"principles": len(principle_ids), "findings": len(finding_ids)},
            },
            project_id=project_id,
            phase="knowledge_seed",
            confidence=0.75,
        )
        mem.close()
    except Exception as e:
        print(f"Knowledge seed failed (non-fatal): {e}", file=sys.stderr)
        sys.exit(0)
    out = {
        "principles": [
            {"description": (p.get("description") or "")[:500], "principle_type": p.get("principle_type"), "metric_score": p.get("metric_score")}
            for p in principles
        ],
        "lateral_principles": [
            {"description": (p.get("description") or "")[:500], "domain": p.get("domain")}
            for p in lateral_principles
        ] if lateral_principles else [],
        "findings": [
            {"finding_key": f.get("finding_key"), "preview": (f.get("content_preview") or "")[:300], "url": f.get("url"), "project_id": f.get("project_id")}
            for f in findings
        ],
        "principle_ids": principle_ids,
        "finding_ids": finding_ids,
    }
    (proj_dir / "prior_knowledge.json").write_text(json.dumps(out, indent=2, ensure_ascii=False))
    sys.exit(0)


if __name__ == "__main__":
    main()
