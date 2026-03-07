"""Shared data loading and LLM helpers for the verify phase."""
import json
import re
from pathlib import Path

from tools.research_common import llm_call, model_for_lane


def model():
    return model_for_lane("verify")


def verify_model():
    return model_for_lane("verify")


def load_sources(proj_path: Path, max_items: int = 50) -> list[dict]:
    sources = []
    for f in (proj_path / "sources").glob("*.json"):
        if f.name.endswith("_content.json"):
            continue
        try:
            sources.append(json.loads(f.read_text()))
        except Exception:
            pass
    return sources[:max_items]


def relevance_score(finding: dict, question: str) -> float:
    q_words = set(re.findall(r'\b[a-z]{3,}\b', question.lower()))
    text = ((finding.get("excerpt") or "") + " " + (finding.get("title") or "")).lower()
    f_words = set(re.findall(r'\b[a-z]{3,}\b', text))
    if not q_words or not f_words:
        return 0.0
    overlap = len(q_words & f_words)
    return overlap / len(q_words)


def load_findings(proj_path: Path, max_items: int = 120, question: str = "") -> list[dict]:
    findings = []
    for f in sorted((proj_path / "findings").glob("*.json")):
        try:
            findings.append(json.loads(f.read_text()))
        except Exception:
            pass
    if question and findings:
        findings.sort(key=lambda f: relevance_score(f, question), reverse=True)
    return findings[:max_items]


def llm_json(system: str, user: str, project_id: str = "", *, model_fn=None) -> dict | list:
    m = (model_fn or model)()
    result = llm_call(m, system, user, project_id=project_id)
    text = (result.text or "").strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*", "", text)
        text = re.sub(r"\s*```$", "", text)
    return json.loads(text)


def load_connect_context(proj_path: Path) -> tuple[str, set[str]]:
    """Load thesis and contradictions from Connect phase. Returns (thesis_current, contradiction_source_urls)."""
    thesis_current = ""
    contradiction_urls: set[str] = set()
    if (proj_path / "thesis.json").exists():
        try:
            th = json.loads((proj_path / "thesis.json").read_text())
            thesis_current = (th.get("current") or "").strip()
        except Exception:
            pass
    if (proj_path / "contradictions.json").exists():
        try:
            data = json.loads((proj_path / "contradictions.json").read_text())
            for c in data.get("contradictions", []):
                for key in ("source_a", "source_b"):
                    val = (c.get(key) or "").strip()
                    if val and (val.startswith("http") or "/" in val):
                        contradiction_urls.add(val)
                    if val and len(val) > 10:
                        contradiction_urls.add(val)
        except Exception:
            pass
    return thesis_current, contradiction_urls


def load_source_metadata(proj_path: Path, max_items: int = 50) -> list[dict]:
    summaries = []
    for f in (proj_path / "sources").glob("*.json"):
        if f.name.endswith("_content.json"):
            continue
        try:
            d = json.loads(f.read_text())
            url = (d.get("url") or "").strip()
            title = (d.get("title") or "").strip()
            desc = (d.get("description") or "").strip()
            if url and (title or desc):
                summaries.append({"url": url, "title": title, "snippet": desc[:300]})
        except Exception:
            pass
    return summaries[:max_items]
