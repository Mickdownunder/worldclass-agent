#!/usr/bin/env python3
"""
Create follow-up research projects from "Suggested Next Steps" in a completed report.
Usage: research_auto_followup.py <project_id>
Env: RESEARCH_AUTO_FOLLOWUP=1 to enable (caller checks), RESEARCH_MAX_FOLLOWUPS=3
"""
import json
import os
import re
import sys
from pathlib import Path

OPERATOR_ROOT = Path(os.environ.get("OPERATOR_ROOT", "/root/operator"))
sys.path.insert(0, str(OPERATOR_ROOT))
from tools.june_handoff_client import submit_research_start

RESEARCH = OPERATOR_ROOT / "research"
MAX_FOLLOWUPS = int(os.environ.get("RESEARCH_MAX_FOLLOWUPS", "3"))


def main():
    if len(sys.argv) < 2:
        print("Usage: research_auto_followup.py <project_id>", file=sys.stderr)
        sys.exit(2)
    parent_project_id = sys.argv[1].strip()
    proj_dir = RESEARCH / parent_project_id
    if not proj_dir.is_dir():
        print(f"Project not found: {parent_project_id}", file=sys.stderr)
        sys.exit(1)
    parent_project = json.loads((proj_dir / "project.json").read_text(encoding="utf-8"))
    parent_research_mode = str((parent_project.get("config") or {}).get("research_mode") or "standard").strip().lower()
    if parent_research_mode not in {"standard", "frontier", "discovery"}:
        parent_research_mode = "standard"
    reports_dir = proj_dir / "reports"
    if not reports_dir.is_dir():
        print("No reports dir", file=sys.stderr)
        sys.exit(0)
    md_files = sorted(reports_dir.glob("*.md"), reverse=True)
    if not md_files:
        print("No report found", file=sys.stderr)
        sys.exit(0)
    report_path = md_files[0]
    report_text = report_path.read_text(encoding="utf-8", errors="replace")
    # Extract "5) Suggested Next Steps" section if present
    match = re.search(r"5\)\s*Suggested Next Steps\s*\n(.*?)(?=\n#|\n\d\)|\Z)", report_text, re.DOTALL | re.IGNORECASE)
    section = (match.group(1).strip() if match else report_text)[:6000]
    prompt = f"""Based on this research report section (Suggested Next Steps or full report), output 2-3 concrete follow-up research questions.
Each question must be one sentence, specific, and researchable (web/academic search).
Output ONLY valid JSON with this structure: {{"questions": ["question 1", "question 2", ...]}}
No other text.

Report excerpt:
{section}"""

    def parse_questions(text: str):
        t = (text or "").strip()
        if t.startswith("```"):
            t = re.sub(r"^```(?:json)?\s*", "", t)
            t = re.sub(r"\s*```$", "", t)
        data = json.loads(t)
        return list(data.get("questions") or [])[:MAX_FOLLOWUPS]

    questions = []
    # 1) Try OpenAI (if key set)
    api_key = os.environ.get("OPENAI_API_KEY")
    if api_key:
        try:
            from openai import OpenAI
            client = OpenAI(api_key=api_key)
            model = os.environ.get("RESEARCH_SYNTHESIS_MODEL", "gpt-4.1-mini")
            resp = client.responses.create(model=model, input=prompt)
            text = (resp.output_text or "").strip()
            questions = parse_questions(text)
        except Exception as e:
            err_str = str(e).lower()
            if "429" in err_str or "quota" in err_str:
                print("OpenAI quota exceeded, trying Gemini fallback...", file=sys.stderr)
            else:
                print(f"OpenAI follow-up failed: {e}", file=sys.stderr)

    # 2) Fallback: Gemini via research_common (e.g. when OpenAI 429)
    if not questions:
        try:
            from tools.research_common import llm_call
            fallback_model = os.environ.get("RESEARCH_FOLLOWUP_FALLBACK_MODEL", "gemini-2.5-flash")
            result = llm_call(fallback_model, "You output only valid JSON.", prompt, project_id="")
            questions = parse_questions(result.text or "")
        except Exception as e:
            print(f"LLM follow-up failed: {e}", file=sys.stderr)
            sys.exit(0)
    if not questions:
        print("No follow-up questions extracted", file=sys.stderr)
        sys.exit(0)
    for q in questions:
        q = (q or "").strip()
        if not q or len(q) < 10:
            continue
        try:
            payload = submit_research_start(
                q,
                source_command="research_auto_followup",
                research_mode=parent_research_mode,
                run_until_done=True,
                parent_project_id=parent_project_id,
            )
            new_project_id = str(payload.get("projectId") or "").strip()
            if not new_project_id:
                continue
            print(f"Started full run: {new_project_id} (Follow-up von {parent_project_id}) — {q[:60]}...")
        except Exception as e:
            print(f"Error: {e}", file=sys.stderr)
    print("Auto-follow-up done.")


if __name__ == "__main__":
    main()
