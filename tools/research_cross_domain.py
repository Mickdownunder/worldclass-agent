#!/usr/bin/env python3
"""
Find cross-domain links: pairs of findings from different projects with high semantic similarity.
Writes cross_links to Memory and outputs JSON insights for notification.

Usage:
  research_cross_domain.py [--threshold 0.75] [--max-pairs 20]
"""
import json
import math
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from lib.memory import Memory


def cosine_similarity(a: list[float], b: list[float]) -> float:
    if not a or not b or len(a) != len(b):
        return 0.0
    dot = sum(x * y for x, y in zip(a, b))
    na = math.sqrt(sum(x * x for x in a))
    nb = math.sqrt(sum(x * x for x in b))
    if na == 0 or nb == 0:
        return 0.0
    return dot / (na * nb)


def main():
    threshold = 0.75
    max_pairs = 20
    argv = sys.argv[1:]
    if "--threshold" in argv:
        i = argv.index("--threshold") + 1
        if i < len(argv):
            threshold = float(argv[i])
    if "--max-pairs" in argv:
        i = argv.index("--max-pairs") + 1
        if i < len(argv):
            max_pairs = int(argv[i])

    memory = Memory()
    rows = memory.get_research_findings_with_embeddings()
    if len(rows) < 2:
        print(json.dumps({"insights": [], "message": "Not enough embedded findings"}))
        return 0

    # Parse embeddings
    findings = []
    for r in rows:
        try:
            emb = json.loads(r["embedding_json"]) if r.get("embedding_json") else None
            if emb:
                findings.append({**r, "embedding": emb})
        except Exception:
            pass

    # Group by project
    by_project: dict[str, list] = {}
    for f in findings:
        by_project.setdefault(f["project_id"], []).append(f)

    if len(by_project) < 2:
        print(json.dumps({"insights": [], "message": "Need findings from at least 2 projects"}))
        return 0

    # Cross-project pairs above threshold
    insights = []
    projects = list(by_project.keys())
    for i in range(len(projects)):
        for j in range(i + 1, len(projects)):
            pa, pb = projects[i], projects[j]
            for fa in by_project[pa]:
                for fb in by_project[pb]:
                    sim = cosine_similarity(fa["embedding"], fb["embedding"])
                    if sim >= threshold:
                        memory.insert_cross_link(
                            finding_a_id=fa["id"],
                            finding_b_id=fb["id"],
                            project_a=pa,
                            project_b=pb,
                            similarity=round(sim, 4),
                        )
                        insights.append({
                            "project_a": pa,
                            "project_b": pb,
                            "similarity": round(sim, 4),
                            "preview_a": (fa.get("content_preview") or "")[:200],
                            "preview_b": (fb.get("title") or fb.get("content_preview") or "")[:200],
                        })
                        if len(insights) >= max_pairs:
                            break
                if len(insights) >= max_pairs:
                    break
            if len(insights) >= max_pairs:
                break
        if len(insights) >= max_pairs:
            break

    print(json.dumps({"insights": insights, "count": len(insights)}, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
