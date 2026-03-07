# Plumber fix routines: shell syntax, missing dependency, repeated failures, rollback, patches.
from __future__ import annotations

import difflib
import json
import os
import re
import subprocess
from datetime import datetime, timezone
from pathlib import Path

from . import constants
from . import diagnose
from . import fingerprints


def _utcnow() -> str:
    return fingerprints._utcnow()


class FixResult:
    def __init__(self, fixed: bool, diagnosis: str, action: str,
                 patch_path: str | None = None, details: dict | None = None):
        self.fixed = fixed
        self.diagnosis = diagnosis
        self.action = action
        self.patch_path = patch_path
        self.details = details or {}

    def to_dict(self) -> dict:
        return {
            "fixed": self.fixed,
            "diagnosis": self.diagnosis,
            "action": self.action,
            "patch_path": self.patch_path,
            **self.details,
        }


def _is_safe_path(path: Path) -> bool:
    rp = path.resolve()
    return any(rp.is_relative_to(root.resolve()) for root in constants.ALLOWED_FIX_ROOTS)


def _save_patch(filename: str, original: str, fixed: str, meta: dict) -> Path:
    constants.PATCHES_DIR.mkdir(parents=True, exist_ok=True)
    diff = difflib.unified_diff(
        original.splitlines(keepends=True),
        fixed.splitlines(keepends=True),
        fromfile=f"a/{filename}",
        tofile=f"b/{filename}",
    )
    patch_content = "".join(diff)
    ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    patch_path = constants.PATCHES_DIR / f"{ts}_{Path(filename).stem}.patch"
    patch_path.write_text(
        f"# Plumber patch — {_utcnow()}\n"
        f"# Reason: {meta.get('reason', 'unknown')}\n"
        f"# Diagnosis: {meta.get('diagnosis', '')[:200]}\n\n"
        + patch_content
    )
    meta_path = patch_path.with_suffix(".json")
    meta["patch_file"] = str(patch_path)
    meta["created_at"] = _utcnow()
    meta_path.write_text(json.dumps(meta, indent=2, default=str))
    return patch_path


def fix_shell_syntax(script_path: Path, governance_level: int = 2) -> FixResult:
    diag = diagnose.diagnose_shell_syntax(script_path)
    if diag["ok"]:
        return FixResult(False, "No syntax error found", "none")
    if not _is_safe_path(script_path):
        return FixResult(False, diag["errors"], "blocked — file outside safe zone")
    original = script_path.read_text()
    lines = original.splitlines(keepends=True)
    err_line = diag.get("line")
    errors_text = diag.get("errors", "")
    fixed_content = None
    fix_description = ""
    if any(kw in errors_text for kw in ["unexpected token", "unexpected end of file", "syntax error"]):
        fix_content_result = _fix_block_balance(lines, err_line, errors_text)
        if fix_content_result:
            fixed_content, fix_description = fix_content_result
    if fixed_content is None and ("unexpected EOF" in errors_text or "unexpected end of file" in errors_text or "unterminated" in errors_text.lower()):
        fix_content_result = _fix_unterminated(lines, err_line, errors_text)
        if fix_content_result:
            fixed_content, fix_description = fix_content_result
    if fixed_content is None:
        if constants.LLM_FIX_ENABLED:
            return FixResult(
                False,
                f"Syntax error at line {err_line}: {errors_text} (LLM fix available if llm_fn provided)",
                "diagnose_only — no auto-fix pattern, try llm_code_fix()",
                details={"errors": errors_text, "line": err_line, "llm_fixable": True},
            )
        return FixResult(
            False,
            f"Syntax error at line {err_line}: {errors_text}",
            "diagnose_only — no auto-fix pattern matched",
            details={"errors": errors_text, "line": err_line},
        )
    import tempfile
    with tempfile.NamedTemporaryFile(mode="w", suffix=".sh", delete=False) as tmp:
        tmp.write(fixed_content)
        tmp_path = tmp.name
    try:
        verify = subprocess.run(["bash", "-n", tmp_path], capture_output=True, text=True, timeout=10)
        if verify.returncode != 0:
            return FixResult(
                False,
                f"Fix attempted but verification failed: {verify.stderr.strip()}",
                "fix_failed_verification",
                details={"original_error": errors_text, "fix_attempted": fix_description},
            )
    finally:
        os.unlink(tmp_path)
    patch_path = _save_patch(
        script_path.name, original, fixed_content,
        {"reason": "shell_syntax_fix", "diagnosis": errors_text,
         "fix": fix_description, "file": str(script_path)},
    )
    if governance_level >= 3:
        script_path.write_text(fixed_content)
        return FixResult(
            True, f"Fixed: {fix_description}",
            "applied",
            patch_path=str(patch_path),
            details={"line": err_line, "verified": True},
        )
    else:
        return FixResult(
            False, f"Fix ready (dry-run): {fix_description}",
            "dry_run — patch saved, governance < 3",
            patch_path=str(patch_path),
            details={"line": err_line, "verified": True, "governance": governance_level},
        )


def _fix_block_balance(lines: list[str], err_line: int | None, errors_text: str):
    content = "".join(lines)
    in_heredoc = False
    heredoc_end = ""
    if_count = 0
    fi_count = 0
    case_count = 0
    esac_count = 0
    while_for_count = 0
    done_count = 0
    for line in lines:
        stripped = line.strip()
        if in_heredoc:
            if stripped == heredoc_end:
                in_heredoc = False
            continue
        hd = re.search(r"<<-?\s*['\"]?(\w+)['\"]?", line)
        if hd:
            heredoc_end = hd.group(1)
            in_heredoc = True
        shell_part = stripped.split("#")[0].strip() if "#" in stripped else stripped
        if re.match(r'^if\s', shell_part) or re.match(r'^if\s', stripped):
            if_count += 1
        if shell_part in ("fi", "fi;") or re.match(r'^fi\b', shell_part):
            fi_count += 1
        if re.match(r'^case\s', shell_part):
            case_count += 1
        if shell_part in ("esac", "esac;") or re.match(r'^esac\b', shell_part):
            esac_count += 1
        if re.match(r'^(while|for)\s', shell_part):
            while_for_count += 1
        if shell_part in ("done", "done;") or re.match(r'^done\b', shell_part):
            done_count += 1

    def _insert_idx():
        if err_line and err_line <= len(lines):
            return err_line - 1
        return len(lines)

    if if_count > fi_count:
        missing = if_count - fi_count
        idx = _insert_idx()
        indent = "    "
        if idx < len(lines):
            m = re.match(r'^(\s*)', lines[idx])
            if m:
                indent = m.group(1)
        for _ in range(missing):
            lines.insert(idx, f"{indent}fi\n")
        return "".join(lines), f"Inserted {missing} missing 'fi' at line {idx + 1}"
    if case_count > esac_count:
        missing = case_count - esac_count
        idx = _insert_idx()
        indent = "    "
        for _ in range(missing):
            lines.insert(idx, f"{indent}esac\n")
        return "".join(lines), f"Inserted {missing} missing 'esac' at line {idx + 1}"
    if while_for_count > done_count:
        missing = while_for_count - done_count
        idx = _insert_idx()
        indent = "    "
        for _ in range(missing):
            lines.insert(idx, f"{indent}done\n")
        return "".join(lines), f"Inserted {missing} missing 'done' at line {idx + 1}"
    return None


def _fix_unterminated(lines: list[str], err_line: int | None, errors_text: str):
    if err_line and err_line <= len(lines):
        line = lines[err_line - 1]
        single_q = line.count("'") % 2
        double_q = line.count('"') % 2
        if single_q:
            lines[err_line - 1] = line.rstrip("\n") + "'\n"
            return "".join(lines), f"Added closing single quote at line {err_line}"
        if double_q:
            lines[err_line - 1] = line.rstrip("\n") + '"\n'
            return "".join(lines), f"Added closing double quote at line {err_line}"
    return None


def fix_missing_dependency(module: str, pip_name: str, governance_level: int = 2) -> FixResult:
    pip_lower = pip_name.lower().replace("-", "_")
    if pip_lower not in {p.lower().replace("-", "_") for p in constants.TRUSTED_PACKAGES}:
        return FixResult(
            False,
            f"Module '{module}' (pip: {pip_name}) not in trusted package list",
            "blocked — untrusted package",
            details={"module": module, "pip_name": pip_name,
                     "hint": f"Add '{pip_name}' to TRUSTED_PACKAGES in plumber to allow auto-install"},
        )
    if governance_level < 3:
        return FixResult(
            False,
            f"Would install '{pip_name}' (governance {governance_level} < 3)",
            "dry_run — needs governance 3",
            details={"module": module, "pip_name": pip_name},
        )
    python = str(constants.VENV / "bin" / "python3") if (constants.VENV / "bin" / "python3").exists() else "python3"
    pip_cmd = [python, "-m", "pip", "install", pip_name]
    try:
        r = subprocess.run(pip_cmd, capture_output=True, text=True, timeout=60)
        if r.returncode == 0:
            verify = subprocess.run(
                [python, "-c", f"import {module}"],
                capture_output=True, text=True, timeout=10,
            )
            if verify.returncode == 0:
                return FixResult(
                    True,
                    f"Installed '{pip_name}' — import {module} OK",
                    "applied",
                    details={"module": module, "pip_name": pip_name, "verified": True},
                )
            else:
                return FixResult(
                    False,
                    f"Installed '{pip_name}' but import {module} still fails: {verify.stderr[:200]}",
                    "fix_failed_verification",
                    details={"module": module, "pip_name": pip_name},
                )
        else:
            return FixResult(
                False,
                f"pip install {pip_name} failed: {r.stderr[:200]}",
                "install_failed",
                details={"module": module, "pip_name": pip_name},
            )
    except Exception as e:
        return FixResult(
            False,
            f"pip install {pip_name} error: {e}",
            "install_error",
            details={"module": module, "pip_name": pip_name},
        )


def fix_repeated_failures(
    workflow: str,
    failures: list[dict],
    governance_level: int = 2,
    llm_fn=None,
) -> FixResult:
    logs = []
    for f in failures[:3]:
        log = diagnose.read_job_log(f.get("job_dir", ""), tail=60)
        if log:
            logs.append(log)
    if not logs:
        fingerprints.record_fingerprint(workflow, "no logs available", fix_attempted=False,
                           fix_succeeded=False, action="no_logs",
                           category="repeated_failures")
        return FixResult(False, "No logs available for analysis", "no_logs")
    error_summary = diagnose._extract_error_from_logs(logs)
    nr = fingerprints.classify_non_repairable(error_summary)
    if nr:
        reason_code, explanation = nr
        fingerprints.mark_non_repairable(workflow, error_summary, reason_code)
        fingerprints.record_fingerprint(workflow, error_summary, fix_attempted=False,
                           fix_succeeded=False, action=f"non_repairable:{reason_code}",
                           category="repeated_failures")
        return FixResult(
            False,
            f"Non-repairable: {explanation}",
            f"non_repairable:{reason_code}",
            details={"reason": reason_code, "explanation": explanation,
                     "error_summary": error_summary[:300]},
        )
    on_cd, cd_entry = fingerprints.is_on_cooldown(workflow, error_summary)
    if on_cd and cd_entry:
        fingerprints.record_fingerprint(workflow, error_summary, fix_attempted=False,
                           fix_succeeded=False, action="cooldown_skip",
                           category="repeated_failures")
        reason = "non-repairable" if cd_entry.get("non_repairable") else "cooldown active"
        return FixResult(
            False,
            f"Skipped fix — {reason} (fingerprint {cd_entry.get('fingerprint', '?')}, "
            f"{cd_entry.get('fix_attempts', 0)} prior attempts)",
            f"cooldown_skip",
            details={"fingerprint": cd_entry.get("fingerprint"),
                     "prior_attempts": cd_entry.get("fix_attempts", 0),
                     "cooldown_until": cd_entry.get("cooldown_until", "")},
        )
    script = constants.WORKFLOWS / f"{workflow}.sh"
    if script.exists():
        syntax_diag = diagnose.diagnose_shell_syntax(script)
        if not syntax_diag["ok"]:
            result = fix_shell_syntax(script, governance_level)
            fingerprints.record_fingerprint(workflow, error_summary, fix_attempted=result.applied,
                               fix_succeeded=result.applied, action=result.action,
                               category="shell_syntax")
            return result
    fnf_match = re.search(r"FileNotFoundError.*No such file.*: '([^']+)'", error_summary)
    if fnf_match:
        missing_path = fnf_match.group(1)
        fingerprints.record_fingerprint(workflow, error_summary, fix_attempted=False,
                           fix_succeeded=False, action="diagnose_only",
                           category="missing_file")
        return FixResult(
            False,
            f"Jobs fail because file is missing: {missing_path}",
            "diagnose_only — missing file detected",
            details={"missing_file": missing_path, "error_pattern": "FileNotFoundError"},
        )
    mod_match = re.search(r"ModuleNotFoundError.*No module named '([^']+)'", error_summary)
    if mod_match:
        module = mod_match.group(1)
        fingerprints.record_fingerprint(workflow, error_summary, fix_attempted=False,
                           fix_succeeded=False, action="diagnose_only",
                           category="missing_module")
        return FixResult(
            False,
            f"Jobs fail due to missing Python module: {module}",
            "diagnose_only — missing module",
            details={"missing_module": module, "error_pattern": "ModuleNotFoundError",
                     "suggested_fix": f"pip install {module}"},
        )
    if "timeout" in error_summary.lower():
        fingerprints.record_fingerprint(workflow, error_summary, fix_attempted=False,
                           fix_succeeded=False, action="diagnose_only",
                           category="timeout")
        return FixResult(
            False,
            f"Jobs fail due to timeout: {error_summary[:200]}",
            "diagnose_only — timeout",
            details={"error_pattern": "timeout"},
        )
    if llm_fn:
        try:
            from . import llm_fix as _llm_fix
            analysis = llm_fn(
                system="You are a DevOps expert. Analyze these job failure logs and identify the root cause. Return JSON: {\"root_cause\": \"...\", \"fix_suggestion\": \"...\", \"file_to_fix\": \"path or null\", \"confidence\": 0.0-1.0}",
                user=f"Workflow: {workflow}\nError: {error_summary}\n\nRecent logs:\n" + "\n---\n".join(logs[:2])[:4000],
            )
            fingerprints.record_fingerprint(workflow, error_summary, fix_attempted=False,
                               fix_succeeded=False, action="llm_analysis",
                               category="llm_diagnosis")
            return FixResult(
                False,
                f"LLM analysis: {analysis.get('root_cause', 'unknown')}",
                "diagnose_only — LLM analysis",
                details={
                    "llm_root_cause": analysis.get("root_cause"),
                    "llm_fix_suggestion": analysis.get("fix_suggestion"),
                    "llm_file": analysis.get("file_to_fix"),
                    "llm_confidence": analysis.get("confidence"),
                },
            )
        except Exception:
            pass
    if constants.LLM_FIX_ENABLED and llm_fn:
        from . import llm_fix as _llm_fix
        llm_result = _llm_fix.llm_fix_from_job_failure(workflow, failures, governance_level, llm_fn)
        if llm_result is not None:
            fp_action = "llm_fix_applied" if llm_result.applied else "llm_fix_failed"
            fingerprints.record_fingerprint(workflow, error_summary, fix_attempted=True,
                               fix_succeeded=llm_result.applied, action=fp_action,
                               category="llm_fix")
            return llm_result
    fingerprints.record_fingerprint(workflow, error_summary, fix_attempted=False,
                       fix_succeeded=False, action="no_fix_pattern",
                       category="unknown")
    return FixResult(
        False,
        f"Repeated failures ({len(failures)}x) in {workflow}: {error_summary[:200]}",
        "diagnose_only — no matching fix pattern",
        details={"error_summary": error_summary},
    )


def rollback_if_still_failing(patch_meta_path: Path) -> dict | None:
    if not patch_meta_path.exists():
        return None
    try:
        meta = json.loads(patch_meta_path.read_text())
    except (json.JSONDecodeError, OSError):
        return None
    if meta.get("reason") != "llm_code_fix":
        return None
    created = meta.get("created_at", "")
    if not created:
        return None
    file_fixed = meta.get("file", "")
    wf_name = None
    if "/workflows/" in file_fixed:
        wf_name = Path(file_fixed).stem
    if not wf_name:
        return None
    post_fix_failures = 0
    if constants.JOBS.exists():
        for job_file in sorted(constants.JOBS.glob("*/*/job.json"), reverse=True)[:20]:
            try:
                j = json.loads(job_file.read_text())
                if j.get("workflow_id") != wf_name:
                    continue
                if j.get("status") != "FAILED":
                    continue
                job_ts = j.get("created_at", "")
                if job_ts > created:
                    post_fix_failures += 1
            except (json.JSONDecodeError, OSError):
                continue
    if post_fix_failures >= 2:
        patch_file = meta.get("patch_file", "")
        if patch_file:
            result = rollback_patch(patch_file)
            result["reason"] = f"Auto-rollback: {wf_name} still failing ({post_fix_failures}x) after LLM fix"
            return result
    return None


def _compute_patch_metrics(patches: list[dict]) -> dict:
    total = len(patches)
    if total == 0:
        return {
            "total_patches": 0, "files_affected": 0, "total_loc_changed": 0,
            "reverts": 0, "success_rate_pct": 0, "by_category": {},
        }
    files_affected = set()
    total_loc = 0
    reverts = 0
    successes = 0
    by_cat: dict[str, dict] = {}
    for p in patches:
        f = p.get("file", "")
        if f:
            files_affected.add(f)
        loc = p.get("loc_changed", p.get("changed_lines", 0))
        total_loc += loc
        cat = p.get("category", p.get("type", "unknown"))
        c = by_cat.setdefault(cat, {"count": 0, "loc": 0, "reverts": 0, "successes": 0})
        c["count"] += 1
        c["loc"] += loc
        if p.get("reverted"):
            reverts += 1
            c["reverts"] += 1
        elif p.get("verified", True):
            successes += 1
            c["successes"] += 1
    return {
        "total_patches": total,
        "files_affected": len(files_affected),
        "total_loc_changed": total_loc,
        "reverts": reverts,
        "success_rate_pct": round(successes / total * 100, 1) if total > 0 else 0,
        "by_category": by_cat,
    }


def rollback_patch(patch_path: str) -> dict:
    pp = Path(patch_path)
    if not pp.exists():
        return {"ok": False, "error": "Patch file not found"}
    meta_path = pp.with_suffix(".json")
    if not meta_path.exists():
        return {"ok": False, "error": "Patch meta not found"}
    meta = json.loads(meta_path.read_text())
    target_file = Path(meta.get("file", ""))
    if not target_file.exists():
        return {"ok": False, "error": f"Target file not found: {target_file}"}
    try:
        result = subprocess.run(
            ["patch", "-R", str(target_file), str(pp)],
            capture_output=True, text=True, timeout=10,
        )
        if result.returncode == 0:
            return {"ok": True, "rolled_back": str(target_file)}
        return {"ok": False, "error": result.stderr.strip()}
    except Exception as e:
        return {"ok": False, "error": str(e)}


def list_patches() -> list[dict]:
    patches = []
    if not constants.PATCHES_DIR.exists():
        return patches
    for meta_file in sorted(constants.PATCHES_DIR.glob("*.json"), reverse=True):
        try:
            patches.append(json.loads(meta_file.read_text()))
        except (json.JSONDecodeError, OSError):
            continue
    return patches
