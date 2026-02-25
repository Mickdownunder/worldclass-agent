#!/usr/bin/env python3
"""
Create follow-up research projects from "Suggested Next Steps" in a completed report.
Usage: research_auto_followup.py <project_id>
Env: RESEARCH_AUTO_FOLLOWUP=1 to enable (caller checks), RESEARCH_MAX_FOLLOWUPS=3
"""
import json
import os
import re
import subprocess
import sys
from pathlib import Path

OPERATOR_ROOT = Path(os.environ.get("OPERATOR_ROOT", "/root/operator"))
OP = OPERATOR_ROOT / "bin" / "op"
RESEARCH = OPERATOR_ROOT / "research"
MAX_FOLLOWUPS = int(os.environ.get("RESEARCH_MAX_FOLLOWUPS", "3"))


def main():
    if len(sys.argv) < 2:
        print("Usage: research_auto_followup.py <project_id>", file=sys.stderr)
        sys.exit(2)
    project_id = sys.argv[1].strip()
    proj_dir = RESEARCH / project_id
    if not proj_dir.is_dir():
        print(f"Project not found: {project_id}", file=sys.stderr)
        sys.exit(1)
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
    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        print("OPENAI_API_KEY not set, skipping follow-up", file=sys.stderr)
        sys.exit(0)
    from openai import OpenAI
    client = OpenAI(api_key=api_key)
    model = os.environ.get("RESEARCH_SYNTHESIS_MODEL", "gpt-4.1-mini")
    prompt = f"""Based on this research report section (Suggested Next Steps or full report), output 2-3 concrete follow-up research questions.
Each question must be one sentence, specific, and researchable (web/academic search).
Output ONLY valid JSON with this structure: {{"questions": ["question 1", "question 2", ...]}}
No other text.

Report excerpt:
{section}"""
    try:
        resp = client.responses.create(model=model, input=prompt)
        text = (resp.output_text or "").strip()
        if text.startswith("```"):
            text = re.sub(r"^```(?:json)?\s*", "", text)
            text = re.sub(r"\s*```$", "", text)
        data = json.loads(text)
        questions = list(data.get("questions") or [])[:MAX_FOLLOWUPS]
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
            job_dir = subprocess.check_output(
                [str(OP), "job", "new", "--workflow", "research-init", "--request", q],
                text=True,
                timeout=10,
                cwd=str(OPERATOR_ROOT),
                env={**os.environ},
            ).strip()
            subprocess.Popen(
                [str(OP), "run", job_dir, "--timeout", "120"],
                cwd=str(OPERATOR_ROOT),
                env=os.environ,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            print(f"Created follow-up: {q[:80]}...")
        except subprocess.CalledProcessError as e:
            print(f"Failed to create job for: {q[:50]}... ({e})", file=sys.stderr)
        except Exception as e:
            print(f"Error: {e}", file=sys.stderr)
    print("Auto-follow-up done.")


if __name__ == "__main__":
    main()
