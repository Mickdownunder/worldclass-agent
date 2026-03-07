"""Utility-ranked retrieval (MemRL-inspired). Phase 1: semantic/keyword candidates; Phase 2: utility re-rank."""
import os

from .embedding import embed_query
from . import search as search_module


def retrieve_with_utility_impl(
    memory,
    query: str,
    memory_type: str,
    k: int = 10,
    context_key: str | None = None,
    domain: str | None = None,
) -> list[dict]:
    """
    Phase 1: semantic/keyword candidates. Phase 2: utility re-rank.
    Findings are filtered by query. When RESEARCH_MEMORY_SEMANTIC=1 and OPENAI_API_KEY is set,
    principles/findings with embedding_json use cosine similarity.
    Optional: RESEARCH_MEMORY_PRINCIPLE_DOMAIN_FILTER=1 enables domain-first principle retrieval with global fallback.
    """
    ctx = (context_key or query or "").strip().lower()[:180]
    try:
        lam = float(os.environ.get("RESEARCH_MEMORY_UTILITY_LAMBDA", "0.6"))
    except Exception:
        lam = 0.6
    lam = max(0.1, min(0.9, lam))
    principle_domain_filter_enabled = os.environ.get("RESEARCH_MEMORY_PRINCIPLE_DOMAIN_FILTER", "0") == "1"
    normalized_domain = (domain or "").strip().lower()
    query_embedding = embed_query(query or "")
    if memory_type == "principle":
        if principle_domain_filter_enabled and normalized_domain:
            scoped_limit = max(k * 4, k + 2)
            candidates = memory._principles.search(
                query,
                limit=scoped_limit,
                domain=normalized_domain,
                query_embedding=query_embedding,
            )
            min_scoped = max(2, min(k, 4))
            if len(candidates) < min_scoped:
                global_candidates = memory._principles.search(
                    query,
                    limit=max(k * 5, k + 6),
                    query_embedding=query_embedding,
                )
                seen_ids = {c.get("id") for c in candidates if c.get("id")}
                for gc in global_candidates:
                    gid = gc.get("id")
                    if gid and gid in seen_ids:
                        continue
                    candidates.append(gc)
                    if len(candidates) >= (k * 5):
                        break
        else:
            candidates = memory._principles.search(query, limit=k * 5, query_embedding=query_embedding)
    elif memory_type == "reflection":
        candidates = search_module.search_reflections(memory._conn, query, limit=k * 5)
    elif memory_type == "finding":
        candidates = memory._research.search_by_query(query, limit=k * 5, query_embedding=query_embedding)
    else:
        return []

    for c in candidates:
        mid = c.get("id")
        if not mid:
            continue
        util_row = memory._utility.get(memory_type, mid, context_key=ctx or None)
        util_score = util_row["utility_score"] if util_row else 0.5
        c["utility_score"] = util_score
        similarity = c.get("similarity_score", c.get("relevance_score", c.get("relevance", 0.5)))
        if not isinstance(similarity, (int, float)):
            similarity = 0.5
        c["similarity_score"] = float(similarity)
        combined = (1.0 - lam) * float(similarity) + lam * float(util_score)
        if memory_type == "principle" and principle_domain_filter_enabled and normalized_domain:
            domain_val = str(c.get("domain") or "").strip().lower()
            if domain_val == normalized_domain:
                combined += 0.05
        c["combined_score"] = round(min(1.0, combined), 6)

    candidates.sort(key=lambda x: x.get("combined_score", 0), reverse=True)
    selected = candidates[:k]
    for c in selected:
        mid = c.get("id")
        if mid:
            memory._utility.record_retrieval(memory_type, str(mid), context_key=ctx or None)
    return selected
