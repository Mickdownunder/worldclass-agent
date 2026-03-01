#!/usr/bin/env python3
"""
Index research findings into Memory with OpenAI embeddings (text-embedding-3-small).
Admission gate: only findings that pass research_memory_policy are stored as 'accepted' and embedded.
Quarantined/rejected are stored with admission_state but not embedded.

Usage:
  research_embed.py [project_id]
  If project_id omitted, indexes all projects under research/.
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from tools.research_common import research_root, load_secrets
from tools.research_memory_policy import decide, reason
from lib.memory import Memory
from tools.research_budget import track_usage

EMBEDDING_MODEL = "text-embedding-3-small"


def get_embedding(text: str, client) -> list[float]:
    if not text or not text.strip():
        return []
    resp = client.embeddings.create(model=EMBEDDING_MODEL, input=text[:8000])
    return resp.data[0].embedding


def _scores_for_finding(project_dir: Path, data: dict) -> dict:
    """Build scores from project verify artifacts (source_reliability, claim_verification) or defaults."""
    url = (data.get("url") or "").strip()
    reliability_score = 0.5
    verification_status = "unknown"
    evidence_count = 0
    verify_dir = project_dir / "verify"
    if (verify_dir / "source_reliability.json").exists():
        try:
            rel = json.loads((verify_dir / "source_reliability.json").read_text())
            for s in rel.get("sources", []):
                if s.get("url", "").strip() == url:
                    reliability_score = float(s.get("reliability_score", 0.5))
                    break
        except Exception:
            pass
    if (verify_dir / "claim_verification.json").exists():
        try:
            cv = json.loads((verify_dir / "claim_verification.json").read_text())
            for c in cv.get("claims", []):
                urls = c.get("supporting_sources") or []
                if url in urls or any(url in u for u in urls if isinstance(u, str)):
                    evidence_count += 1
            if evidence_count >= 2:
                verification_status = "confirmed"
            elif evidence_count == 1:
                verification_status = "single_source"
        except Exception:
            pass
    importance_score = 0.5
    if data.get("confidence") is not None:
        importance_score = float(data["confidence"])
    return {
        "reliability_score": reliability_score,
        "importance_score": importance_score,
        "verification_status": verification_status,
        "evidence_count": evidence_count,
    }


def main():
    from openai import OpenAI
    secrets = load_secrets()
    client = OpenAI(api_key=secrets.get("OPENAI_API_KEY"))
    memory = Memory()
    research = research_root()
    if not research.exists():
        print("No research root", file=sys.stderr)
        return 0

    project_ids = [p.name for p in research.iterdir() if p.is_dir() and p.name.startswith("proj-")]
    if len(sys.argv) >= 2:
        project_ids = [sys.argv[1]]

    indexed = 0
    for project_id in project_ids:
        proj_dir = research / project_id
        findings_dir = proj_dir / "findings"
        if not findings_dir.exists():
            continue
        for f in findings_dir.glob("*.json"):
            try:
                data = json.loads(f.read_text())
            except Exception:
                continue
            content = (data.get("excerpt") or data.get("title") or data.get("url") or "")[:4000]
            if not content:
                continue
            finding_key = f.stem
            existing = memory._conn.execute(
                "SELECT id FROM research_findings WHERE project_id=? AND finding_key=?", (project_id, finding_key)
            ).fetchone()
            if existing:
                continue
            scores = _scores_for_finding(proj_dir, data)
            decision = decide(scores)
            rev = reason(scores, decision)
            scores["verification_status"] = scores.get("verification_status") or "unknown"
            if decision == "accepted":
                try:
                    emb = get_embedding(content, client)
                    emb_json = json.dumps(emb) if emb else None
                    if emb and project_id:
                        try:
                            # ~4 chars per token for embedding input
                            track_usage(project_id, "text-embedding-3-small", max(1, len(content) // 4), 0)
                        except Exception:
                            pass
                except Exception as e:
                    print(f"Embedding failed {finding_key}: {e}", file=sys.stderr)
                    emb_json = None
                    decision = "quarantined"
                    rev = "embedding_failed"
            else:
                emb_json = None
            memory.insert_research_finding(
                project_id=project_id,
                finding_key=finding_key,
                content_preview=content[:500],
                embedding_json=emb_json,
                url=data.get("url"),
                title=data.get("title"),
                relevance_score=scores.get("relevance_score"),
                reliability_score=scores.get("reliability_score"),
                verification_status=scores.get("verification_status"),
                evidence_count=scores.get("evidence_count"),
                importance_score=scores.get("importance_score"),
                admission_state=decision,
            )
            memory.record_admission_event(project_id, finding_key, decision, rev, scores)
            if decision == "accepted":
                indexed += 1
    print(f"Indexed {indexed} findings (accepted)", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
