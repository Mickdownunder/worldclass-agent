"""Load and sort findings/sources for synthesis. No ledger or outline logic."""
import json
import os
import re
from pathlib import Path

from tools.synthesis.constants import MAX_FINDINGS, SOURCE_CONTENT_CHARS, _model


def _relevance_score(finding: dict, question: str) -> float:
    """Score finding relevance to research question via keyword overlap."""
    q_words = set(re.findall(r'\b[a-z]{3,}\b', question.lower()))
    text = ((finding.get("excerpt") or "") + " " + (finding.get("title") or "")).lower()
    f_words = set(re.findall(r'\b[a-z]{3,}\b', text))
    if not q_words or not f_words:
        return 0.0
    return len(q_words & f_words) / len(q_words)


def _embed_texts(texts: list[str], project_id: str = "") -> list[list[float]]:
    """Embed texts with OpenAI text-embedding-3-small. Returns one embedding per input; [] on failure or if disabled."""
    if not texts:
        return []
    try:
        from openai import OpenAI
        from tools.research_common import load_secrets
        secrets = load_secrets()
        key = secrets.get("OPENAI_API_KEY")
        if not key:
            return []
        client = OpenAI(api_key=key)
        model = os.environ.get("RESEARCH_EMBEDDING_MODEL", "text-embedding-3-small")
        out: list[list[float]] = []
        batch_size = 20
        for i in range(0, len(texts), batch_size):
            slice_ = texts[i : i + batch_size]
            batch = [t[:8000] for t in slice_ if (t or "").strip()]
            if not batch:
                out.extend([[]] * len(slice_))
                continue
            resp = client.embeddings.create(model=model, input=batch)
            by_idx = {item.index: item.embedding for item in resp.data}
            idx_in_batch = 0
            for t in slice_:
                if (t or "").strip():
                    out.append(by_idx.get(idx_in_batch, []))
                    idx_in_batch += 1
                else:
                    out.append([])
        if project_id and out:
            try:
                from tools.research_budget import track_usage
                total = sum(len(e) for e in out) * 4  # rough token estimate
                track_usage(project_id, "embedding", total, 0)
            except Exception:
                pass
        return out[:len(texts)]
    except Exception:
        return []


def _semantic_relevance_sort(
    question: str, findings: list[dict], project_id: str,
) -> list[dict]:
    """Re-sort findings by hybrid (keyword + semantic) when RESEARCH_SYNTHESIS_SEMANTIC=1. Returns unchanged on failure."""
    if not question or not findings or os.environ.get("RESEARCH_SYNTHESIS_SEMANTIC") != "1":
        return findings
    q_emb = _embed_texts([question], project_id)
    if not q_emb or not q_emb[0]:
        return findings
    q_vec = q_emb[0]
    texts = [((f.get("excerpt") or "") + " " + (f.get("title") or ""))[:8000].strip() for f in findings]
    f_embs = _embed_texts(texts, project_id)
    if len(f_embs) != len(findings) or not all(f_embs):
        return findings

    def cosine(a: list[float], b: list[float]) -> float:
        if not a or not b or len(a) != len(b):
            return 0.0
        dot = sum(x * y for x, y in zip(a, b))
        na = sum(x * x for x in a) ** 0.5
        nb = sum(x * x for x in b) ** 0.5
        if na * nb == 0:
            return 0.0
        return dot / (na * nb)

    keyword_scores = [_relevance_score(f, question) for f in findings]
    semantic_scores = [max(0.0, cosine(q_vec, e)) for e in f_embs]
    alpha = 0.5
    try:
        alpha = float(os.environ.get("RESEARCH_SYNTHESIS_SEMANTIC_WEIGHT", "0.5"))
        alpha = max(0.0, min(1.0, alpha))
    except ValueError:
        pass
    combined = [alpha * s + (1 - alpha) * k for k, s in zip(keyword_scores, semantic_scores)]
    indexed = list(zip(combined, findings))
    indexed.sort(key=lambda x: x[0], reverse=True)
    return [f for _, f in indexed]


def _load_findings(proj_path: Path, max_items: int = MAX_FINDINGS, question: str = "") -> list[dict]:
    findings = []
    for f in sorted((proj_path / "findings").glob("*.json")):
        try:
            findings.append(json.loads(f.read_text()))
        except Exception:
            pass
    if question and findings:
        findings.sort(key=lambda f: _relevance_score(f, question), reverse=True)
    return findings[:max_items]


def _load_sources(proj_path: Path) -> list[dict]:
    sources = []
    for f in (proj_path / "sources").glob("*.json"):
        if "_content" in f.name:
            continue
        try:
            sources.append(json.loads(f.read_text()))
        except Exception:
            pass
    return sources


def _load_source_content(proj_path: Path, url: str, max_chars: int = SOURCE_CONTENT_CHARS) -> str:
    import hashlib
    key = hashlib.sha256(url.encode()).hexdigest()[:12]
    cf = proj_path / "sources" / f"{key}_content.json"
    if not cf.exists():
        return ""
    try:
        d = json.loads(cf.read_text())
        text = (d.get("text") or d.get("abstract") or "").strip()
        return text[:max_chars]
    except Exception:
        return ""
