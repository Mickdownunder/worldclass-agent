#!/usr/bin/env python3
"""
Research Orchestrator (June-level autonomy).
Runs periodically (e.g. via cron). Gathers done reports + sandbox results + running projects,
asks an LLM what to do next, then starts new research runs and/or sandbox experiments in background.

Usage: research_orchestrator.py [--dry-run]
Env: OPERATOR_ROOT, OPENAI_API_KEY (or uses Gemini fallback), RESEARCH_ORCHESTRATOR_MAX_RESEARCH=3, RESEARCH_ORCHESTRATOR_MAX_SANDBOX=2
"""
import json
import os
import re
import subprocess
import sys
from pathlib import Path

OPERATOR_ROOT = Path(os.environ.get("OPERATOR_ROOT", "/root/operator"))
sys.path.insert(0, str(OPERATOR_ROOT))
RESEARCH = OPERATOR_ROOT / "research"
OP = OPERATOR_ROOT / "bin" / "op"
RUN_UNTIL_DONE = OPERATOR_ROOT / "tools" / "run-research-cycle-until-done.sh"
TOOLS = OPERATOR_ROOT / "tools"
MAX_RESEARCH = int(os.environ.get("RESEARCH_ORCHESTRATOR_MAX_RESEARCH", "3"))
MAX_SANDBOX = int(os.environ.get("RESEARCH_ORCHESTRATOR_MAX_SANDBOX", "2"))
REPORT_EXCERPT_CHARS = 4000
EXPERIMENT_SUMMARY_CHARS = 1500


def get_project_phase(proj_dir: Path) -> str:
    pj = proj_dir / "project.json"
    if not pj.is_file():
        return ""
    try:
        return json.loads(pj.read_text(encoding="utf-8")).get("phase", "")
    except Exception:
        return ""


def get_latest_report_excerpt(proj_dir: Path) -> str:
    reports_dir = proj_dir / "reports"
    if not reports_dir.is_dir():
        return ""
    md_files = sorted(reports_dir.glob("*.md"), reverse=True)
    if not md_files:
        return ""
    text = md_files[0].read_text(encoding="utf-8", errors="replace")
    # Prefer "Suggested Next Steps" and Executive Summary
    for pattern in [
        r"5\)\s*Suggested Next Steps\s*\n(.*?)(?=\n#|\n\d\)|\Z)",
        r"## Executive Summary\s*\n(.*?)(?=\n##|\Z)",
    ]:
        m = re.search(pattern, text, re.DOTALL | re.IGNORECASE)
        if m:
            return (m.group(1).strip() or text)[:REPORT_EXCERPT_CHARS]
    return text[:REPORT_EXCERPT_CHARS]


def get_experiment_summary(proj_dir: Path) -> str:
    exp_path = proj_dir / "experiment.json"
    if not exp_path.is_file():
        return ""
    try:
        data = json.loads(exp_path.read_text(encoding="utf-8"))
        gate = data.get("gate") or {}
        out = f"objective_met={gate.get('objective_met')}; stdout_last={repr((data.get('final_stdout') or '')[:500])}"
        return out[:EXPERIMENT_SUMMARY_CHARS]
    except Exception:
        return ""


def gather_context() -> tuple[str, list[str], list[str]]:
    """Returns (context_text, list of done project_ids, list of running project_ids)."""
    done_ids = []
    running = []
    parts = []

    for d in sorted(RESEARCH.iterdir()):
        if not d.is_dir() or not d.name.startswith("proj-"):
            continue
        pid = d.name
        phase = get_project_phase(d)
        if phase == "done":
            done_ids.append(pid)
            report_excerpt = get_latest_report_excerpt(d)
            exp_summary = get_experiment_summary(d)
            parts.append(f"### Done: {pid}\nReport excerpt:\n{report_excerpt[:3000]}\n")
            if exp_summary:
                parts.append(f"Sandbox/experiment: {exp_summary}\n")
        elif phase and phase not in ("cancelled", "abandoned"):
            running.append(pid)
            parts.append(f"### Running: {pid} (phase={phase})\n")

    context = "\n".join(parts) if parts else "No projects yet."
    running_line = f"Currently running projects: {', '.join(running)}\n" if running else "No projects currently running.\n"
    context = running_line + "\n" + context
    return context, done_ids, running


def llm_decide(context: str) -> dict:
    """Call LLM; return {"research_questions": [...], "sandbox_project_ids": [...]}."""
    prompt = f"""You are the research orchestrator. You see the current state of all research projects (done reports + sandbox results, and running projects).
Decide the next actions to maximize research progress and validation.

Context:
{context[:12000]}

Output ONLY valid JSON with this structure (no markdown, no explanation):
{{"research_questions": ["concrete research question 1", "question 2"], "sandbox_project_ids": ["proj-YYYYMMDD-xxxx"]}}

Rules:
- research_questions: 0 to {MAX_RESEARCH} new follow-up research questions (specific, one sentence, researchable). Only suggest if there are clear gaps or "Suggested Next Steps" not yet covered.
- sandbox_project_ids: 0 to {MAX_SANDBOX} done project IDs that should get an additional sandbox experiment run to validate or deepen results. Only include IDs that are in the "Done" list above and would benefit from more sandbox validation.
- If nothing useful to do, return {{"research_questions": [], "sandbox_project_ids": []}}.
"""

    def parse_out(text: str) -> dict:
        t = (text or "").strip()
        if t.startswith("```"):
            t = re.sub(r"^```(?:json)?\s*", "", t)
            t = re.sub(r"\s*```$", "", t)
        data = json.loads(t)
        return {
            "research_questions": list(data.get("research_questions") or [])[:MAX_RESEARCH],
            "sandbox_project_ids": list(data.get("sandbox_project_ids") or [])[:MAX_SANDBOX],
        }

    api_key = os.environ.get("OPENAI_API_KEY")
    if api_key:
        try:
            from openai import OpenAI
            client = OpenAI(api_key=api_key)
            model = os.environ.get("RESEARCH_ORCHESTRATOR_MODEL", "gpt-4.1-mini")
            resp = client.responses.create(model=model, input=prompt)
            text = (resp.output_text or "").strip()
            return parse_out(text)
        except Exception as e:
            print(f"OpenAI orchestrator failed: {e}", file=sys.stderr)

    try:
        from tools.research_common import llm_call
        result = llm_call(
            os.environ.get("RESEARCH_ORCHESTRATOR_FALLBACK_MODEL", "gemini-2.5-flash"),
            "You output only valid JSON.",
            prompt,
            project_id="",
        )
        return parse_out(result.text or "")
    except Exception as e:
        print(f"LLM orchestrator failed: {e}", file=sys.stderr)
        return {"research_questions": [], "sandbox_project_ids": []}


def start_research_question(question: str, dry_run: bool) -> str | None:
    """Create research-init job, run init, then start run-research-cycle-until-done in background. Returns new project_id or None."""
    if dry_run:
        print(f"[dry-run] Would start research: {question[:60]}...", file=sys.stderr)
        return None
    try:
        out = subprocess.check_output(
            [str(OP), "job", "new", "--workflow", "research-init", "--request", question],
            text=True,
            timeout=10,
            cwd=str(OPERATOR_ROOT),
            env=os.environ,
        ).strip()
        job_dir = out.split("\n")[-1].strip() if out else ""
        if not job_dir:
            return None
        subprocess.run(
            [str(OP), "run", job_dir, "--timeout", "120"],
            cwd=str(OPERATOR_ROOT),
            env=os.environ,
            timeout=130,
            capture_output=True,
        )
        pid_file = Path(job_dir) / "artifacts" / "project_id.txt"
        if not pid_file.is_file():
            return None
        new_project_id = pid_file.read_text(encoding="utf-8").strip()
        if not new_project_id:
            return None
        subprocess.Popen(
            ["bash", str(RUN_UNTIL_DONE), new_project_id],
            cwd=str(OPERATOR_ROOT),
            env=os.environ,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            start_new_session=True,
        )
        print(f"Started research: {new_project_id} — {question[:50]}...", file=sys.stderr)
        return new_project_id
    except Exception as e:
        print(f"Failed to start research for '{question[:40]}...': {e}", file=sys.stderr)
        return None


def start_sandbox_for_project(project_id: str, dry_run: bool) -> bool:
    if dry_run:
        print(f"[dry-run] Would run sandbox for {project_id}", file=sys.stderr)
        return True
    proj_dir = RESEARCH / project_id
    if not proj_dir.is_dir() or get_project_phase(proj_dir) != "done":
        print(f"Skip sandbox for {project_id} (not done or missing)", file=sys.stderr)
        return False
    try:
        subprocess.Popen(
            [sys.executable, str(TOOLS / "research_experiment.py"), project_id],
            cwd=str(OPERATOR_ROOT),
            env=os.environ,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.PIPE,
            start_new_session=True,
        )
        print(f"Started sandbox experiment for {project_id}", file=sys.stderr)
        return True
    except Exception as e:
        print(f"Failed to start sandbox for {project_id}: {e}", file=sys.stderr)
        return False


def main():
    dry_run = "--dry-run" in sys.argv
    if dry_run:
        print("Orchestrator dry-run.", file=sys.stderr)

    context, done_ids, running = gather_context()
    if not done_ids and not running:
        print("No research projects found. Nothing to orchestrate.", file=sys.stderr)
        return 0

    decision = llm_decide(context)
    questions = [q.strip() for q in (decision.get("research_questions") or []) if q and len(q) >= 10]
    sandbox_ids = [s for s in (decision.get("sandbox_project_ids") or []) if s in done_ids]

    started = []
    for q in questions:
        pid = start_research_question(q, dry_run)
        if pid:
            started.append(("research", pid, q[:50]))
    for sid in sandbox_ids:
        if start_sandbox_for_project(sid, dry_run):
            started.append(("sandbox", sid, ""))

    if started:
        print(json.dumps({"started": started, "dry_run": dry_run}))
    return 0


if __name__ == "__main__":
    sys.exit(main())
