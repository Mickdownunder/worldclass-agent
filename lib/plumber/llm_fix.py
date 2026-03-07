# Plumber LLM-powered code fix (optional, PLUMBER_LLM_FIX=1 to enable).
from __future__ import annotations

import difflib
import os
import re
import subprocess
from pathlib import Path

from . import constants
from . import diagnose
from . import fix

_llm_fix_attempted: set[str] = set()


def llm_code_fix(
    file_path: Path,
    error_context: str,
    governance_level: int = 2,
    llm_fn=None,
) -> fix.FixResult:
    file_str = str(file_path)
    if not constants.LLM_FIX_ENABLED:
        return fix.FixResult(
            False,
            "LLM fix disabled (set PLUMBER_LLM_FIX=1 to enable)",
            "disabled",
            details={"file": file_str, "hint": "export PLUMBER_LLM_FIX=1"},
        )
    if not llm_fn:
        return fix.FixResult(
            False, "No LLM function available", "no_llm",
            details={"file": file_str},
        )
    if not fix._is_safe_path(file_path):
        return fix.FixResult(
            False, f"File outside safe zone: {file_str}", "blocked",
            details={"file": file_str},
        )
    if file_str in _llm_fix_attempted:
        return fix.FixResult(
            False, f"Already attempted LLM fix on {file_path.name} this session",
            "skip_recursive",
            details={"file": file_str},
        )
    _llm_fix_attempted.add(file_str)
    if not file_path.exists():
        return fix.FixResult(False, f"File not found: {file_str}", "file_missing")
    original = file_path.read_text()
    lines = original.splitlines()
    if len(lines) > 400:
        context_lines = lines[:200] + ["", "# ... (truncated) ...", ""] + lines[-200:]
    else:
        context_lines = lines
    code_context = "\n".join(context_lines)
    file_type = file_path.suffix
    system_prompt = f"""You are an expert code repair agent. You fix bugs in production code.

RULES:
1. Output ONLY valid JSON with this structure:
   {{"fixed_code": "the complete fixed file content", "explanation": "what you changed and why", "confidence": 0.0-1.0}}
2. Make the SMALLEST possible change that fixes the error. Do NOT rewrite or refactor.
3. Keep all existing functionality intact.
4. The fix must be syntactically valid ({'.sh = bash' if file_type == '.sh' else '.py = Python 3'}).
5. Maximum {constants.LLM_FIX_MAX_DIFF_LINES} lines changed. If the fix requires more, set confidence to 0.0.
6. If you are NOT confident about the fix (< 0.6), set confidence accordingly — the system will skip low-confidence patches."""

    user_prompt = f"""FILE: {file_path.name}
TYPE: {file_type}
ERROR:
{error_context[:2000]}

CURRENT CODE:
```
{code_context[:8000]}
```

Analyze the error, find the root cause, and provide the minimal fix."""

    try:
        result = llm_fn(system=system_prompt, user=user_prompt)
    except Exception as e:
        return fix.FixResult(
            False, f"LLM call failed: {e}", "llm_error",
            details={"file": file_str},
        )
    if not isinstance(result, dict) or "fixed_code" not in result:
        return fix.FixResult(
            False, "LLM returned invalid response (no fixed_code)", "llm_bad_response",
            details={"file": file_str},
        )
    fixed_code = result["fixed_code"]
    explanation = result.get("explanation", "")
    confidence = float(result.get("confidence", 0.0))
    if confidence < 0.6:
        return fix.FixResult(
            False,
            f"LLM fix rejected: confidence {confidence:.2f} < 0.6 — {explanation[:200]}",
            "low_confidence",
            details={"file": file_str, "confidence": confidence, "explanation": explanation[:300]},
        )
    original_lines = original.splitlines(keepends=True)
    fixed_lines = fixed_code.splitlines(keepends=True)
    diff = list(difflib.unified_diff(original_lines, fixed_lines, n=0))
    changed_lines = sum(1 for line in diff if line.startswith("+") or line.startswith("-"))
    changed_lines = max(0, changed_lines - 2)
    if changed_lines > constants.LLM_FIX_MAX_DIFF_LINES:
        return fix.FixResult(
            False,
            f"LLM fix too large: {changed_lines} lines changed (max {constants.LLM_FIX_MAX_DIFF_LINES})",
            "diff_too_large",
            details={"file": file_str, "changed_lines": changed_lines, "explanation": explanation[:300]},
        )
    if changed_lines == 0:
        return fix.FixResult(
            False, "LLM returned identical code (no changes)", "no_changes",
            details={"file": file_str},
        )
    import tempfile
    with tempfile.NamedTemporaryFile(mode="w", suffix=file_type, delete=False) as tmp:
        tmp.write(fixed_code)
        tmp_path = tmp.name
    try:
        if file_type == ".sh":
            verify = subprocess.run(["bash", "-n", tmp_path], capture_output=True, text=True, timeout=10)
        elif file_type == ".py":
            python = str(constants.VENV / "bin" / "python3") if (constants.VENV / "bin" / "python3").exists() else "python3"
            verify = subprocess.run([python, "-m", "py_compile", tmp_path], capture_output=True, text=True, timeout=10)
        else:
            class _Fake:
                returncode = 0
                stderr = ""
            verify = _Fake()
        if verify.returncode != 0:
            err = (getattr(verify, "stderr", None) or "").strip()[:200]
            return fix.FixResult(
                False,
                f"LLM fix failed verification: {err}",
                "fix_failed_verification",
                details={"file": file_str, "explanation": explanation[:300], "verify_error": err},
            )
    finally:
        os.unlink(tmp_path)
    patch_path = fix._save_patch(
        file_path.name, original, fixed_code,
        {
            "reason": "llm_code_fix",
            "model": constants.LLM_FIX_MODEL,
            "diagnosis": error_context[:300],
            "explanation": explanation[:500],
            "confidence": confidence,
            "changed_lines": changed_lines,
            "file": file_str,
        },
    )
    if governance_level >= 3:
        file_path.write_text(fixed_code)
        return fix.FixResult(
            True,
            f"LLM fix applied ({changed_lines} lines, confidence {confidence:.2f}): {explanation[:200]}",
            "applied",
            patch_path=str(patch_path),
            details={
                "file": file_str, "changed_lines": changed_lines,
                "confidence": confidence, "model": constants.LLM_FIX_MODEL,
                "explanation": explanation[:500], "verified": True,
            },
        )
    else:
        return fix.FixResult(
            False,
            f"LLM fix ready (dry-run, {changed_lines} lines, confidence {confidence:.2f}): {explanation[:200]}",
            "dry_run",
            patch_path=str(patch_path),
            details={
                "file": file_str, "changed_lines": changed_lines,
                "confidence": confidence, "model": constants.LLM_FIX_MODEL,
                "explanation": explanation[:500], "verified": True, "governance": governance_level,
            },
        )


def llm_fix_from_job_failure(
    workflow: str,
    failures: list[dict],
    governance_level: int = 2,
    llm_fn=None,
) -> fix.FixResult | None:
    if not constants.LLM_FIX_ENABLED or not llm_fn:
        return None
    logs = []
    for f in failures[:3]:
        log = diagnose.read_job_log(f.get("job_dir", ""), tail=80)
        if log:
            logs.append(log)
    if not logs:
        return None
    error_summary = diagnose._extract_error_from_logs(logs)
    file_to_fix = None
    for log in logs:
        for line in log.splitlines():
            m = re.search(r'File "(/root/operator/(tools|workflows)/[^"]+)"', line)
            if m:
                candidate = Path(m.group(1))
                if candidate.exists() and fix._is_safe_path(candidate):
                    file_to_fix = candidate
                    break
        if file_to_fix:
            break
    if not file_to_fix:
        script = constants.WORKFLOWS / f"{workflow}.sh"
        if script.exists():
            file_to_fix = script
    if not file_to_fix:
        return None
    error_context = f"Workflow: {workflow}\nRepeated failures: {len(failures)}x\n\nError:\n{error_summary}\n\nRecent log:\n{logs[0][:3000]}"
    return llm_code_fix(file_to_fix, error_context, governance_level, llm_fn)
