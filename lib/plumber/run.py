# Plumber master entry point: run_plumber orchestrates all diagnostic and fix categories.
from __future__ import annotations

import json
from pathlib import Path

from . import constants
from . import diagnose
from . import fix
from . import fingerprints
from . import llm_fix


def run_plumber(
    intent: str = "diagnose-and-fix",
    target: str | None = None,
    governance_level: int = 2,
    llm_fn=None,
) -> dict:
    constants.PLUMBER_DIR.mkdir(parents=True, exist_ok=True)
    results: list[dict] = []
    issues_found = 0
    issues_fixed = 0
    categories: dict[str, dict] = {}

    if constants.LLM_FIX_ENABLED and constants.PATCHES_DIR.exists():
        for meta_file in constants.PATCHES_DIR.glob("*.json"):
            rb = fix.rollback_if_still_failing(meta_file)
            if rb and rb.get("ok"):
                results.append({
                    "type": "auto_rollback",
                    "severity": constants.WARNING,
                    "fixed": True,
                    "diagnosis": rb.get("reason", "Auto-rollback of bad LLM fix"),
                    "action": "rolled_back",
                    "target": rb.get("rolled_back", ""),
                })
                issues_found += 1
                issues_fixed += 1

    cat_shell = {"status": "clean", "issues": []}
    if constants.WORKFLOWS.exists():
        for script in sorted(constants.WORKFLOWS.glob("*.sh")):
            diag = diagnose.diagnose_shell_syntax(script)
            if not diag["ok"]:
                issues_found += 1
                fix_result = fix.fix_shell_syntax(script, governance_level)
                entry = {"type": "shell_syntax", "target": str(script), **fix_result.to_dict()}
                results.append(entry)
                cat_shell["issues"].append(entry)
                cat_shell["status"] = "issues_found"
                fingerprints.record_fingerprint(
                    script.stem, diag.get("errors", "shell syntax error"),
                    fix_attempted=fix_result.fixed, fix_succeeded=fix_result.fixed,
                    action=fix_result.action, category="shell_syntax",
                )
                if fix_result.fixed:
                    issues_fixed += 1
    categories["shell_syntax"] = cat_shell

    cat_failures = {"status": "clean", "issues": []}
    repeated = diagnose.diagnose_repeated_failures()
    for r in repeated:
        wf = r["workflow"]
        if target and target != wf:
            continue
        issues_found += 1
        fix_result = fix.fix_repeated_failures(wf, r["failures"], governance_level, llm_fn)
        entry = {"type": "repeated_failures", "target": wf, "fail_count": r["fail_count"], **fix_result.to_dict()}
        results.append(entry)
        cat_failures["issues"].append(entry)
        cat_failures["status"] = "issues_found"
        if fix_result.fixed:
            issues_fixed += 1
    categories["repeated_failures"] = cat_failures

    cat_python = {"status": "clean", "issues": []}
    py_issues = diagnose.diagnose_python_tools()
    for issue in py_issues:
        issues_found += 1
        entry = {"type": "python_tool", **issue}
        results.append(entry)
        cat_python["issues"].append(entry)
        cat_python["status"] = "issues_found"
        fingerprints.record_fingerprint(
            issue.get("file", "unknown"), issue.get("error", "python tool error"),
            fix_attempted=False, fix_succeeded=False,
            action="diagnose_only", category="python_tools",
        )
    categories["python_tools"] = cat_python

    cat_deps = {"status": "clean", "issues": []}
    dep_issues = diagnose.diagnose_dependencies()
    for issue in dep_issues:
        issues_found += 1
        mod = issue.get("module", "")
        pip_name = issue.get("pip_name", mod)
        fix_result = fix.fix_missing_dependency(mod, pip_name, governance_level)
        entry = {"type": "dependency", **issue, **fix_result.to_dict()}
        results.append(entry)
        cat_deps["issues"].append(entry)
        cat_deps["status"] = "issues_found"
        fingerprints.record_fingerprint(
            mod, f"missing dependency: {mod}",
            fix_attempted=fix_result.fixed, fix_succeeded=fix_result.fixed,
            action=fix_result.action, category="dependencies",
        )
        if fix_result.fixed:
            issues_fixed += 1
            cat_deps["status"] = "fixed"
    categories["dependencies"] = cat_deps

    cat_refs = {"status": "clean", "issues": [], "dead_tools": []}
    ref_info = diagnose.diagnose_tool_references()
    for miss in ref_info.get("missing_refs", []):
        issues_found += 1
        diag_msg = f"Workflow references {miss['tool']} but file does not exist"
        entry = {"type": "missing_tool_ref", "target": miss["tool"], "script": miss["script"], "severity": constants.CRITICAL,
                 "fixed": False, "diagnosis": diag_msg, "action": "diagnose_only"}
        results.append(entry)
        cat_refs["issues"].append(entry)
        cat_refs["status"] = "issues_found"
        fingerprints.record_fingerprint(
            miss.get("script", "unknown"), diag_msg,
            fix_attempted=False, fix_succeeded=False,
            action="diagnose_only", category="tool_references",
        )
    cat_refs["dead_tools"] = ref_info.get("dead_tools", [])
    cat_refs["referenced_count"] = ref_info.get("referenced_count", 0)
    if ref_info.get("dead_tools"):
        cat_refs["status"] = "info"
    categories["tool_references"] = cat_refs

    cat_contracts = {"status": "clean", "issues": [], "missing_contracts": []}
    contract_info = diagnose.diagnose_tool_contracts()
    cat_contracts["missing_contracts"] = contract_info.get("missing_contracts", [])
    for tool_name in contract_info.get("missing_contracts", []):
        issues_found += 1
        diag_msg = f"Research tool {tool_name} has no contract in research_tool_registry (env/argv cannot be validated)"
        entry = {"type": "missing_tool_contract", "target": tool_name, "severity": "medium",
                 "fixed": False, "diagnosis": diag_msg, "action": "Add entry to tools/research_tool_registry.py TOOL_CONTRACTS"}
        results.append(entry)
        cat_contracts["issues"].append(entry)
        cat_contracts["status"] = "issues_found"
    if not cat_contracts["issues"]:
        cat_contracts["registered_contracts"] = contract_info.get("registered_contracts", 0)
    categories["tool_contracts"] = cat_contracts

    cat_proc = {"status": "clean", "issues": []}
    proc_info = diagnose.diagnose_processes()
    if proc_info.get("stuck"):
        issues_found += 1
        stuck_procs = [p for group in [proc_info["brain_cycles"], proc_info["brain_reflects"]]
                       for p in group if p.get("stuck")]
        diag_msg = f"{len(stuck_procs)} stuck brain process(es)"
        entry = {
            "type": "stuck_process",
            "severity": constants.CRITICAL,
            "fixed": False,
            "diagnosis": diag_msg,
            "action": "diagnose_only — use 'pkill -f bin/brain' or UI kill button",
            "processes": stuck_procs,
        }
        results.append(entry)
        cat_proc["issues"].append(entry)
        cat_proc["status"] = "issues_found"
        fingerprints.record_fingerprint(
            "brain", diag_msg,
            fix_attempted=False, fix_succeeded=False,
            action="diagnose_only", category="processes",
        )
    if proc_info.get("zombie_count", 0) > 0:
        diag_msg = f"{proc_info['zombie_count']} zombie process(es) on system"
        entry = {
            "type": "zombie_processes",
            "severity": constants.WARNING,
            "fixed": False,
            "diagnosis": diag_msg,
            "action": "diagnose_only",
        }
        results.append(entry)
        cat_proc["issues"].append(entry)
        if cat_proc["status"] == "clean":
            cat_proc["status"] = "issues_found"
        fingerprints.record_fingerprint(
            "system", diag_msg,
            fix_attempted=False, fix_succeeded=False,
            action="diagnose_only", category="processes",
        )
    cat_proc["cycle_count"] = len(proc_info.get("brain_cycles", []))
    cat_proc["reflect_count"] = len(proc_info.get("brain_reflects", []))
    categories["processes"] = cat_proc

    cat_venv = {"status": "clean", "issues": []}
    venv_issues = diagnose.diagnose_venv()
    for issue in venv_issues:
        issues_found += 1
        entry = {"type": "venv", **issue}
        results.append(entry)
        cat_venv["issues"].append(entry)
        cat_venv["status"] = "issues_found"
        fingerprints.record_fingerprint(
            "venv", issue.get("error", issue.get("check", "venv issue")),
            fix_attempted=False, fix_succeeded=False,
            action="diagnose_only", category="venv",
        )
    categories["venv"] = cat_venv

    if target and Path(target).exists() and Path(target).suffix == ".sh":
        target_path = Path(target)
        if fix._is_safe_path(target_path):
            diag = diagnose.diagnose_shell_syntax(target_path)
            if not diag["ok"]:
                issues_found += 1
                fix_result = fix.fix_shell_syntax(target_path, governance_level)
                results.append({"type": "targeted_fix", "target": str(target_path), **fix_result.to_dict()})
                if fix_result.fixed:
                    issues_fixed += 1

    clean_count = sum(1 for c in categories.values() if c["status"] == "clean")
    critical_count = sum(1 for r in results if r.get("severity") == constants.CRITICAL)
    warning_count = sum(1 for r in results if r.get("severity") == constants.WARNING)
    fp_stats = fingerprints.get_fingerprint_stats()
    patches = fix.list_patches()
    patch_metrics = fix._compute_patch_metrics(patches)

    report = {
        "timestamp": fingerprints._utcnow(),
        "intent": intent,
        "governance_level": governance_level,
        "issues_found": issues_found,
        "issues_fixed": issues_fixed,
        "categories": categories,
        "summary": {
            "clean": clean_count,
            "total_categories": len(categories),
            "critical": critical_count,
            "warnings": warning_count,
        },
        "results": results,
        "fingerprints": fp_stats,
        "patch_metrics": patch_metrics,
    }
    report_path = constants.PLUMBER_DIR / "last_run.json"
    report_path.write_text(json.dumps(report, indent=2, default=str))
    return report
