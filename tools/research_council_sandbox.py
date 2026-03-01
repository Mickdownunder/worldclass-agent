#!/usr/bin/env python3
"""
After the Research Council writes MASTER_DOSSIER.md, validate its core thesis in the sandbox.
Extracts one testable claim, generates a minimal Python script, runs it in Docker, appends result to dossier.
Usage: research_council_sandbox.py <parent_id>
"""
import json
import os
import re
import sys
from pathlib import Path

OPERATOR_ROOT = Path(os.environ.get("OPERATOR_ROOT", "/root/operator"))
sys.path.insert(0, str(OPERATOR_ROOT))
from tools.research_common import llm_call, model_for_lane
from tools.research_sandbox import run_in_sandbox

RESEARCH = OPERATOR_ROOT / "research"


def _parse_metrics_from_stdout(stdout: str) -> dict | None:
    """Extract METRICS_JSON from sandbox stdout (may span multiple lines)."""
    import re
    idx = (stdout or "").find("METRICS_JSON:")
    if idx < 0:
        return None
    start = stdout.find("{", idx)
    if start < 0:
        return None
    depth = 0
    for i in range(start, len(stdout)):
        if stdout[i] == "{":
            depth += 1
        elif stdout[i] == "}":
            depth -= 1
            if depth == 0:
                try:
                    data = json.loads(stdout[start : i + 1])
                    out = {}
                    if "utility_history" in data:
                        uh = data["utility_history"]
                        out["utility_history"] = [float(x) for x in uh] if isinstance(uh, list) else []
                    out["boundary_violations"] = int(data.get("boundary_violations", -1))
                    out["accepted_mutations"] = int(data.get("accepted_mutations", -1))
                    return out
                except (json.JSONDecodeError, TypeError, ValueError):
                    return None
    return None


def main() -> int:
    if len(sys.argv) < 2:
        print("Usage: research_council_sandbox.py <parent_id>", file=sys.stderr)
        return 2
    parent_id = sys.argv[1].strip()
    parent_dir = RESEARCH / parent_id
    dossier_path = parent_dir / "MASTER_DOSSIER.md"
    if not dossier_path.is_file():
        print("MASTER_DOSSIER.md not found. Run research_council.py first.", file=sys.stderr)
        return 1

    dossier_text = dossier_path.read_text(encoding="utf-8", errors="replace")[:12000]
    model = model_for_lane("synthesize")

    sys_prompt = """You are a research validator. Given a Master Dossier (synthesis report), you do two things in one response:

1. THESIS: In one sentence, state the single most concrete, testable claim or thesis from the dossier (e.g. "Fitness monotonic execution can be simulated by a local optimizer that only accepts improvements").
2. CODE: Then output ONLY valid, self-contained Python 3 code that simulates or tests that thesis. No markdown, no ```. Code must:
   - Run in under 30 seconds
   - Use no external APIs or network
   - Run at least 100 iterations (or steps) of the selection/mutation loop
   - Track: utility per step (or every Nth step to keep list size under 300), count of boundary violations, count of accepted mutations
   - Print at the end either "PASS" or "FAIL" and a one-line result
   - On the last line of output, print exactly: METRICS_JSON: {"utility_history": [list of floats], "boundary_violations": int, "accepted_mutations": int}
   - Start with 'import' or 'print'

Output format exactly:
THESIS: <one sentence>
CODE:
<raw Python code>"""

    user_prompt = f"Master Dossier excerpt:\n{dossier_text}\n\nOutput THESIS and CODE as above."

    try:
        res = llm_call(model, sys_prompt, user_prompt, project_id=parent_id)
        text = (res.text or "").strip()
    except Exception as e:
        print(f"Council sandbox: LLM failed: {e}", file=sys.stderr)
        return 1

    thesis = ""
    code = ""
    if "THESIS:" in text:
        parts = text.split("THESIS:", 1)[-1].split("CODE:", 1)
        thesis = (parts[0].strip().split("\n")[0] or "").strip()
        if len(parts) > 1:
            code = parts[1].strip()
    if not code:
        code = text
    code = re.sub(r"^```\w*\s*", "", code)
    code = re.sub(r"\s*```\s*$", "", code)
    code = code.strip()
    if not code or not code.startswith(("import", "print", "#")):
        print("Council sandbox: No valid code extracted.", file=sys.stderr)
        result = {"thesis": thesis or "(none)", "code": code[:500], "stdout": "", "stderr": "No valid code", "exit_code": -1, "passed": False}
    else:
        sb = run_in_sandbox(code, timeout_seconds=30)
        passed = sb.exit_code == 0 and ("PASS" in sb.stdout or "pass" in sb.stdout.lower())
        result = {
            "thesis": thesis or "(none)",
            "code": code[:2000],
            "stdout": (sb.stdout or "")[-2000:],
            "stderr": (sb.stderr or "")[-1000:],
            "exit_code": sb.exit_code,
            "passed": passed,
        }
        # Parse METRICS_JSON for long-term stability (utility trajectory, boundary violations, monotonicity)
        metrics = _parse_metrics_from_stdout(sb.stdout or "")
        if metrics:
            result["metrics"] = metrics
            # Derived: monotonicity over full run, drift (second half vs first half)
            uh = metrics.get("utility_history") or []
            if len(uh) >= 2:
                monotonic = all(uh[i] <= uh[i + 1] for i in range(len(uh) - 1))
                result["metrics"]["monotonicity_held"] = monotonic
                result["metrics"]["utility_initial"] = uh[0]
                result["metrics"]["utility_final"] = uh[-1]
                mid = len(uh) // 2
                result["metrics"]["utility_drift_2nd_half"] = (sum(uh[mid:]) / (len(uh) - mid)) - (sum(uh[:mid]) / mid) if mid else 0.0

    out_json = parent_dir / "council_sandbox_result.json"
    out_json.write_text(json.dumps(result, indent=2), encoding="utf-8")

    metrics = result.get("metrics") or {}
    metrics_blurb = ""
    if metrics:
        mono = metrics.get("monotonicity_held")
        bv = metrics.get("boundary_violations", -1)
        am = metrics.get("accepted_mutations", -1)
        u0 = metrics.get("utility_initial")
        u1 = metrics.get("utility_final")
        drift = metrics.get("utility_drift_2nd_half")
        drift_s = f"; Drift (2nd vs 1st half): {drift:.4f}" if drift is not None else ""
        metrics_blurb = (
            "\n**Metrics (anti-drift):** "
            f"Monotonicity over run: {mono if mono is not None else 'n/a'}; "
            f"Boundary violations: {bv}; "
            f"Accepted mutations: {am}; "
            f"Utility {u0} → {u1}{drift_s}"
        )
    appendix = f"""

---
## Sandbox Validation (Council Thesis)

**Thesis tested:** {result['thesis']}

**Result:** {"PASS" if result['passed'] else "FAIL"} (exit code {result['exit_code']})
{metrics_blurb}

**Stdout:**
```
{(result['stdout'] or '(empty)')[:1500]}
```

**Stderr:**
```
{(result['stderr'] or '(none)')[:800]}
```
"""
    with open(dossier_path, "a", encoding="utf-8") as f:
        f.write(appendix)
    print(f"Council sandbox: {'PASS' if result['passed'] else 'FAIL'} — result in {out_json}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
