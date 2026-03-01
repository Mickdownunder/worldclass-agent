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
sys.path.insert(0, str(OPERATOR_ROOT))
OP = OPERATOR_ROOT / "bin" / "op"
RESEARCH = OPERATOR_ROOT / "research"
RUN_UNTIL_DONE = OPERATOR_ROOT / "tools" / "run-research-cycle-until-done.sh"
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
            out = subprocess.check_output(
                [str(OP), "job", "new", "--workflow", "research-init", "--request", q],
                text=True,
                timeout=10,
                cwd=str(OPERATOR_ROOT),
                env={**os.environ},
            ).strip()
            job_dir = out.split("\n")[-1].strip() if out else ""
            if not job_dir:
                print("No job dir returned", file=sys.stderr)
                continue
            # Wait for init to finish (like "Forschung starten" in the UI)
            subprocess.run(
                [str(OP), "run", job_dir, "--timeout", "120"],
                cwd=str(OPERATOR_ROOT),
                env=os.environ,
                timeout=130,
                capture_output=True,
            )
            project_id_file = Path(job_dir) / "artifacts" / "project_id.txt"
            if not project_id_file.is_file():
                print(f"No project_id after init for: {q[:50]}...", file=sys.stderr)
                continue
            new_project_id = project_id_file.read_text(encoding="utf-8").strip()
            if not new_project_id:
                continue
            # Link this follow-up to the parent and inherit domain so Memory/strategies stay on theme
            try:
                proj_json = RESEARCH / new_project_id / "project.json"
                if proj_json.is_file():
                    data = json.loads(proj_json.read_text(encoding="utf-8"))
                    data["parent_project_id"] = parent_project_id
                    parent_json = RESEARCH / parent_project_id / "project.json"
                    if parent_json.is_file():
                        parent_data = json.loads(parent_json.read_text(encoding="utf-8"))
                        parent_domain = (parent_data.get("domain") or "").strip()
                        if parent_domain and parent_domain != "general":
                            data["domain"] = parent_domain
                    proj_json.write_text(json.dumps(data, indent=2), encoding="utf-8")
            except Exception as e:
                print(f"Could not set parent_project_id/domain: {e}", file=sys.stderr)
            # Start full research cycle (explore → … → done), same as "Forschung starten"
            subprocess.Popen(
                ["bash", str(RUN_UNTIL_DONE), new_project_id],
                cwd=str(OPERATOR_ROOT),
                env=os.environ,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                start_new_session=True,
            )
            print(f"Started full run: {new_project_id} (Follow-up von {parent_project_id}) — {q[:60]}...")
        except subprocess.CalledProcessError as e:
            print(f"Failed to create job for: {q[:50]}... ({e})", file=sys.stderr)
        except subprocess.TimeoutExpired:
            print(f"Init timeout for: {q[:50]}...", file=sys.stderr)
        except Exception as e:
            print(f"Error: {e}", file=sys.stderr)
    print("Auto-follow-up done.")


if __name__ == "__main__":
    main()
