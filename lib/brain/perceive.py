"""Phase 1: PERCEIVE — Gather current system state."""
import json
import os
from pathlib import Path

from lib import brain_context
from lib.brain.constants import (
    BASE,
    FACTORY,
    GOVERNANCE_LEVELS,
    JOBS,
    KNOWLEDGE,
    RESEARCH,
    WORKFLOWS,
)
from tools.research_control_event import load_last_control_plane_event
from lib.brain.helpers import _utcnow


def perceive_phase(memory, governance_level: int) -> dict:
    """Build a comprehensive perception of the current system state."""
    state = {}

    try:
        import shutil
        disk = shutil.disk_usage("/")
        state["system"] = {
            "disk_used_pct": round(disk.used / disk.total * 100, 1),
            "load": round(os.getloadavg()[0], 2),
            "time": _utcnow(),
        }
    except Exception:
        state["system"] = {"time": _utcnow()}

    recent_jobs = []
    if JOBS.exists():
        job_files = sorted(JOBS.glob("*/*/job.json"), reverse=True)[:10]
        for f in job_files:
            try:
                j = json.loads(f.read_text())
                recent_jobs.append({
                    "id": j.get("id"),
                    "workflow": j.get("workflow_id"),
                    "status": j.get("status"),
                    "duration_s": j.get("duration_s"),
                    "error": j.get("error"),
                })
            except (json.JSONDecodeError, OSError):
                pass
    state["recent_jobs"] = recent_jobs
    state["workflows"] = sorted([f.stem for f in WORKFLOWS.glob("*.sh")]) if WORKFLOWS.exists() else []

    clients = []
    client_dir = FACTORY / "clients"
    if client_dir.exists():
        for f in client_dir.glob("*.json"):
            try:
                c = json.loads(f.read_text())
                clients.append({"id": c["id"], "name": c.get("name"), "topics": c.get("topics", [])})
            except (json.JSONDecodeError, OSError):
                pass
    state["clients"] = clients

    goals_dir = KNOWLEDGE / "goals"
    if goals_dir.exists():
        for f in goals_dir.glob("*.md"):
            try:
                state.setdefault("goals", []).append(f.read_text()[:500])
            except OSError:
                pass
    prio_path = KNOWLEDGE / "priorities.md"
    if prio_path.exists():
        try:
            state["priorities"] = prio_path.read_text()[:500]
        except OSError:
            pass

    research_projects = []
    if RESEARCH.exists():
        def _terminal(s: str) -> bool:
            return s in ("done", "cancelled", "abandoned", "aem_blocked") or (s or "").startswith("failed")

        for proj_dir in sorted(RESEARCH.iterdir(), reverse=True):
            if not proj_dir.is_dir() or not proj_dir.name.startswith("proj-"):
                continue
            proj_json = proj_dir / "project.json"
            if not proj_json.exists():
                continue
            try:
                d = json.loads(proj_json.read_text())
                pid = d.get("id", proj_dir.name)
                parent_id = d.get("parent_project_id")
                council_status = d.get("council_status") or ""
                council_children_running = 0
                if not parent_id and council_status in ("active", "waiting"):
                    for other in RESEARCH.iterdir():
                        if not other.is_dir() or not other.name.startswith("proj-"):
                            continue
                        try:
                            o = json.loads((other / "project.json").read_text())
                            if o.get("parent_project_id") == pid and not _terminal(o.get("status", "")):
                                council_children_running += 1
                        except (json.JSONDecodeError, OSError):
                            pass
                research_projects.append({
                    "id": pid,
                    "question": (d.get("question", "") or "")[:150],
                    "phase": d.get("phase", "?"),
                    "status": d.get("status", "?"),
                    "last_phase_at": d.get("last_phase_at", d.get("created_at", "")),
                    "council_status": council_status,
                    "council_children_running": council_children_running,
                })
            except (json.JSONDecodeError, OSError):
                pass
        def _research_sort(p):
            return (0 if p.get("status") != "done" else 1, p.get("last_phase_at", "") or "")
        research_projects.sort(key=_research_sort)
        state["research_projects"] = research_projects[:25]
    else:
        state["research_projects"] = []

    try:
        last_event = load_last_control_plane_event(event_types=("research_cycle_completed",))
        if last_event:
            state["last_control_plane_event"] = last_event
    except Exception:
        pass

    research_playbooks = []
    playbooks_dir = RESEARCH / "playbooks"
    if playbooks_dir.exists():
        for f in sorted(playbooks_dir.glob("*.json")):
            try:
                d = json.loads(f.read_text())
                research_playbooks.append({
                    "domain": d.get("domain", d.get("id", f.stem)),
                    "name": d.get("name", ""),
                    "strategy": (d.get("strategy", "") or "")[:400],
                    "source": "file",
                })
            except (json.JSONDecodeError, OSError):
                pass
    seen_domains = {p["domain"] for p in research_playbooks}
    for p in memory.all_playbooks():
        domain = p.get("domain", "")
        if domain and domain not in seen_domains:
            research_playbooks.append({
                "domain": domain,
                "name": f"learned:{domain}",
                "strategy": (p.get("strategy", "") or "")[:400],
                "source": "learned",
                "success_rate": p.get("success_rate", 0),
                "version": p.get("version", 1),
            })
            seen_domains.add(domain)
    state["research_playbooks"] = research_playbooks

    state["memory"] = memory.state_summary()
    state["memory"]["recent_reflections"] = [
        r for r in state["memory"].get("recent_reflections", [])
        if (r.get("quality") or 0) >= 0.5
    ]
    goal = ""
    for p in (state.get("research_projects") or []):
        if p.get("status") != "done" and (p.get("question") or "").strip():
            goal = (p.get("question") or "").strip()[:500]
            break
    state["research_context"] = brain_context.compile(memory, query=goal or None)

    try:
        plumber_last = BASE / "plumber" / "last_run.json"
        if plumber_last.exists():
            plumber_report = json.loads(plumber_last.read_text())
            fp = plumber_report.get("fingerprints", {})
            state["plumber_last_scan"] = {
                "timestamp": plumber_report.get("timestamp"),
                "issues_found": plumber_report.get("issues_found", 0),
                "issues_fixed": plumber_report.get("issues_fixed", 0),
                "summary": plumber_report.get("summary", {}),
                "fingerprints": {
                    "total": fp.get("total_fingerprints", 0),
                    "non_repairable": fp.get("non_repairable", 0),
                    "on_cooldown": fp.get("on_cooldown", 0),
                    "fix_success_rate_pct": fp.get("fix_success_rate_pct", 0),
                    "top_recurring": fp.get("top_recurring", [])[:3],
                },
                "patch_metrics": plumber_report.get("patch_metrics", {}),
            }
    except Exception:
        pass

    failure_counts: dict[str, int] = {}
    for j in recent_jobs:
        if j.get("status") == "FAILED":
            wf = j.get("workflow", "unknown")
            failure_counts[wf] = failure_counts.get(wf, 0) + 1
    sick_workflows = {wf: cnt for wf, cnt in failure_counts.items() if cnt >= 2}
    if sick_workflows:
        state["workflow_health"] = {
            "sick_workflows": sick_workflows,
            "hint": "Consider plumber:diagnose-and-fix to fix repeated failures",
        }

    try:
        workflow_trends: dict[str, dict] = {}
        tracked_wfs = set()
        for j in recent_jobs:
            wf = j.get("workflow", "")
            if wf:
                tracked_wfs.add(wf)
        for wf in list(tracked_wfs)[:10]:
            scores = memory.quality_trend(wf, limit=10)
            if len(scores) >= 3:
                values = [s.get("score", 0) for s in scores]
                recent_avg = sum(values[:3]) / 3
                older_avg = sum(values[3:]) / max(len(values[3:]), 1)
                delta = round(recent_avg - older_avg, 3)
                trend = "improving" if delta > 0.05 else "declining" if delta < -0.05 else "stable"
                workflow_trends[wf] = {
                    "recent_avg": round(recent_avg, 3),
                    "older_avg": round(older_avg, 3),
                    "delta": delta,
                    "trend": trend,
                    "sample_size": len(values),
                }
        if workflow_trends:
            state["workflow_trends"] = workflow_trends
    except Exception:
        pass

    state["governance"] = {
        "level": governance_level,
        "mode": GOVERNANCE_LEVELS.get(governance_level, "unknown"),
    }

    n_research = len(state.get("research_projects", []))
    n_not_done = sum(1 for p in state.get("research_projects", []) if p.get("status") != "done")
    memory.record_episode("perceive", f"Perceived system state: {len(recent_jobs)} recent jobs, {len(clients)} clients, {n_research} research projects ({n_not_done} not done)", metadata={"state_keys": list(state.keys())})

    return state
