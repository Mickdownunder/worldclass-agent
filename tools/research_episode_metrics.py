#!/usr/bin/env python3
"""
AEM: Episode metrics (IG/token telemetry) for policy/episode_metrics.jsonl.
One JSON object per line. Must include:
  prior_entropy, posterior_entropy, ig, ig_per_token, ig_mode,
  oracle_integrity_rate, tentative_decay_rate, resolution_rate, stable_claim_rate,
  false_collapse_rate, evidence_delta

IG/token v1 (spec-fixed):
  - forecast|binary|categorical: entropy-based ig; ig_mode = "entropy"
  - structural|explanatory: proxy (disagreement_width_reduction + residual_reduction); ig_mode = "proxy"
  - ig_per_token = ig / max(tokens_spent, 1)

Usage:
  research_episode_metrics.py append <project_id> [--tokens-spent N]
  research_episode_metrics.py last <project_id>   # print last line as JSON
"""
from __future__ import annotations

import json
import math
import sys
from pathlib import Path
from datetime import datetime, timezone

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from tools.research_common import project_dir, load_project, audit_log

EPISODE_METRICS_FILENAME = "episode_metrics.jsonl"
POLICY_DIR = "policy"


def _entropy_from_belief_vector(probs: list[float]) -> float:
    """-sum(p_i * log2(p_i)) for p_i > 0."""
    h = 0.0
    for p in probs:
        if p > 0:
            h -= p * math.log2(p)
    return h


def _belief_vector_from_claims(claims: list[dict], claim_type_filter: set[str] | None = None) -> list[float]:
    """
    Build a simple belief vector from claim support/confidence for entropy-based IG.
    claim_type_filter: if set, only include claims with outcome_type in set (e.g. forecast, binary, categorical).
    """
    if not claims:
        return [1.0]  # single state, entropy 0
    probs = []
    for c in claims:
        if claim_type_filter:
            ot = (c.get("outcome_type") or c.get("claim_type") or "binary").lower()
            if ot not in claim_type_filter:
                continue
        p = float(c.get("p_true") or c.get("confidence") or c.get("claim_support_rate", 0.5))
        if c.get("is_verified") or c.get("state") == "stable":
            p = max(0.01, min(0.99, p))
        else:
            p = 0.5
        probs.append(p)
    if not probs:
        return [1.0]
    # Normalize to distribution (simplified: treat as independent binary beliefs, product distribution entropy ~ sum)
    return probs


def compute_entropy_ig(prior_probs: list[float], posterior_probs: list[float]) -> tuple[float, float, float]:
    """Returns (prior_entropy, posterior_entropy, ig). Uses same-length vectors; if lengths differ, pad with 0.5."""
    n = max(len(prior_probs), len(posterior_probs), 1)
    p_prior = (prior_probs + [0.5] * n)[:n]
    p_post = (posterior_probs + [0.5] * n)[:n]
    # Normalize to simplex for entropy (treat as single distribution over 2^n states -> use average single-axis entropy)
    h_prior = sum(_entropy_from_belief_vector([p, 1 - p]) for p in p_prior) / n
    h_post = sum(_entropy_from_belief_vector([p, 1 - p]) for p in p_post) / n
    ig = max(0.0, h_prior - h_post)
    return round(h_prior, 6), round(h_post, 6), round(ig, 6)


def compute_proxy_ig(prior_width: float, posterior_width: float, prior_residual: float, posterior_residual: float) -> float:
    """Proxy IG for structural/explanatory: disagreement-width shrinkage + residual reduction."""
    w = max(0.0, prior_width - posterior_width)
    r = max(0.0, prior_residual - posterior_residual)
    return round(w + r, 6)


def policy_dir(proj_path: Path) -> Path:
    return proj_path / POLICY_DIR


def episode_metrics_path(proj_path: Path) -> Path:
    return policy_dir(proj_path) / "episode_metrics.jsonl"


def _load_claims_for_metrics(proj_path: Path) -> list[dict]:
    """Load claims from claims/ledger.jsonl or verify/claim_ledger.json for metrics."""
    ledger_jsonl = proj_path / "claims" / "ledger.jsonl"
    if ledger_jsonl.exists():
        claims = []
        for line in ledger_jsonl.read_text().strip().splitlines():
            if not line.strip():
                continue
            try:
                claims.append(json.loads(line))
            except json.JSONDecodeError:
                continue
        if claims:
            return claims
    verify_ledger = proj_path / "verify" / "claim_ledger.json"
    if verify_ledger.exists():
        try:
            data = json.loads(verify_ledger.read_text())
            return data.get("claims", [])
        except Exception:
            pass
    return []


def compute_episode_metrics(
    project_id: str,
    tokens_spent: int = 0,
    prior_probs: list[float] | None = None,
    posterior_probs: list[float] | None = None,
    ig_mode: str = "entropy",
    proxy_ig: float | None = None,
    oracle_integrity_rate: float = 0.0,
    tentative_decay_rate: float = 0.0,
    resolution_rate: float = 0.0,
    stable_claim_rate: float = 0.0,
    false_collapse_rate: float = 0.0,
    evidence_delta: int = 0,
) -> dict:
    """
    Build one episode_metrics record. If prior/posterior not provided, derives from claims (entropy mode).
    """
    proj_path = project_dir(project_id)
    claims = _load_claims_for_metrics(proj_path)
    entropy_types = {"forecast", "binary", "categorical"}
    if prior_probs is not None and posterior_probs is not None and ig_mode == "entropy":
        prior_entropy, posterior_entropy, ig = compute_entropy_ig(prior_probs, posterior_probs)
    elif proxy_ig is not None and ig_mode == "proxy":
        prior_entropy = 0.0
        posterior_entropy = 0.0
        ig = proxy_ig
    else:
        # Derive from claims: simple prior 0.5 each, posterior from verified/state
        p_prior = [0.5] * max(1, len(claims))
        p_post = []
        for c in claims:
            ot = (c.get("outcome_type") or c.get("claim_type") or "binary").lower()
            if ot in entropy_types:
                p = 0.5
                if c.get("is_verified") or (c.get("state") or "").lower() == "stable":
                    p = float(c.get("p_true") or c.get("confidence", 0.7))
                p_post.append(max(0.01, min(0.99, p)))
        if not p_post:
            p_post = [0.5]
        prior_entropy, posterior_entropy, ig = compute_entropy_ig(p_prior[: len(p_post)], p_post)
        ig_mode = "entropy"

    tokens_spent = max(0, int(tokens_spent))
    ig_per_token = round(ig / max(tokens_spent, 1), 6)

    stable_count = sum(1 for c in claims if (c.get("state") or "").lower() == "stable" or c.get("is_verified"))
    total_claims = len(claims) or 1
    if resolution_rate == 0.0 and total_claims:
        resolution_rate = round(stable_count / total_claims, 4)
    if stable_claim_rate == 0.0 and total_claims:
        stable_claim_rate = round(stable_count / total_claims, 4)

    record = {
        "ts": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "project_id": project_id,
        "prior_entropy": prior_entropy,
        "posterior_entropy": posterior_entropy,
        "ig": ig,
        "ig_per_token": ig_per_token,
        "ig_mode": ig_mode,
        "oracle_integrity_rate": round(oracle_integrity_rate, 4),
        "tentative_decay_rate": round(tentative_decay_rate, 4),
        "resolution_rate": round(resolution_rate, 4),
        "stable_claim_rate": round(stable_claim_rate, 4),
        "false_collapse_rate": round(false_collapse_rate, 4),
        "evidence_delta": int(evidence_delta),
        "tokens_spent": tokens_spent,
        "claims_count": len(claims),
    }
    return record


def append_episode_metrics(project_id: str, record: dict | None = None, **kwargs) -> dict:
    """Append one line to policy/episode_metrics.jsonl. Record can be full dict or kwargs for compute_episode_metrics."""
    proj_path = project_dir(project_id)
    policy_dir(proj_path).mkdir(parents=True, exist_ok=True)
    path = episode_metrics_path(proj_path)
    if record is None:
        record = compute_episode_metrics(project_id, **kwargs)
    line = json.dumps(record, ensure_ascii=False) + "\n"
    if path.exists():
        path.write_text(path.read_text(encoding="utf-8") + line, encoding="utf-8")
    else:
        path.write_text(line, encoding="utf-8")
    audit_log(proj_path, "aem_episode_metrics_append", {"ig": record.get("ig"), "ig_per_token": record.get("ig_per_token")})
    return record


def get_last_episode_metrics(project_id: str) -> dict | None:
    """Return last line of episode_metrics.jsonl as dict, or None."""
    path = episode_metrics_path(project_dir(project_id))
    if not path.exists():
        return None
    text = path.read_text().strip()
    if not text:
        return None
    lines = [ln for ln in text.splitlines() if ln.strip()]
    if not lines:
        return None
    try:
        return json.loads(lines[-1])
    except json.JSONDecodeError:
        return None


def main() -> None:
    if len(sys.argv) < 3:
        print("Usage: research_episode_metrics.py append|last <project_id> [--tokens-spent N]", file=sys.stderr)
        sys.exit(2)
    cmd = sys.argv[1].strip().lower()
    project_id = sys.argv[2].strip()
    tokens_spent = 0
    i = 3
    while i < len(sys.argv):
        if sys.argv[i] == "--tokens-spent" and i + 1 < len(sys.argv):
            try:
                tokens_spent = int(sys.argv[i + 1])
            except ValueError:
                pass
            i += 2
        else:
            i += 1
    proj_path = project_dir(project_id)
    if not (proj_path / "project.json").exists():
        print(f"Project not found: {project_id}", file=sys.stderr)
        sys.exit(1)
    if cmd == "append":
        record = append_episode_metrics(project_id, tokens_spent=tokens_spent)
        print(json.dumps(record, indent=2))
    elif cmd == "last":
        last_ = get_last_episode_metrics(project_id)
        print(json.dumps(last_ if last_ else {}, indent=2))
    else:
        print("Unknown command: use append|last", file=sys.stderr)
        sys.exit(2)


if __name__ == "__main__":
    main()
