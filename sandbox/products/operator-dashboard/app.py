#!/usr/bin/env python3
"""Operator Dashboard — FastAPI backend for research pipeline UI."""
import json
import re
import os
from pathlib import Path
from datetime import datetime, timezone
import shutil
from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse, Response
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

app = FastAPI(title="Operator Dashboard", version="2.0")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

OPERATOR_ROOT = Path(os.environ.get("OPERATOR_ROOT", "/root/operator"))
RESEARCH = OPERATOR_ROOT / "research"
JOBS_PATH = OPERATOR_ROOT / "jobs"
_PROJECT_ID_RE = re.compile(r"^proj-\d{8}-[a-f0-9]{8}$")
_JOB_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
_JOB_ID_RE = re.compile(r"^[a-zA-Z0-9_-]+$")


def _validate_project_id(project_id: str) -> Path:
    """Validate project ID format and return path. Prevents path traversal."""
    if not _PROJECT_ID_RE.match(project_id):
        raise HTTPException(status_code=400, detail="Invalid project ID format")
    proj = RESEARCH / project_id
    if not proj.is_dir() or not (proj / "project.json").exists():
        raise HTTPException(status_code=404, detail="Project not found")
    return proj


def _safe_json(path: Path) -> dict | list:
    """Read JSON file safely, return empty dict on error."""
    try:
        return json.loads(path.read_text())
    except (OSError, json.JSONDecodeError):
        return {}


def _get_job_path(date: str, job_id: str) -> Path:
    """Validate date/job_id and return job dir path. Prevents path traversal."""
    if not _JOB_DATE_RE.match(date) or not _JOB_ID_RE.match(job_id):
        raise HTTPException(status_code=400, detail="Invalid date or job_id format")
    job_dir = (JOBS_PATH / date / job_id).resolve()
    jobs_resolved = JOBS_PATH.resolve()
    if not job_dir.is_relative_to(jobs_resolved) or job_dir == jobs_resolved:
        raise HTTPException(status_code=400, detail="Invalid job path")
    if not job_dir.is_dir():
        raise HTTPException(status_code=404, detail="Job not found")
    return job_dir


# ── Jobs API ────────────────────────────────────────────────
@app.get("/api/jobs")
def list_jobs():
    """List all job runs (date, id, workflow_id, status, request) for UI and delete."""
    jobs = []
    if not JOBS_PATH.exists():
        return {"jobs": []}
    for day in sorted(os.listdir(JOBS_PATH), reverse=True)[:60]:
        day_path = JOBS_PATH / day
        if not day_path.is_dir() or not _JOB_DATE_RE.match(day):
            continue
        for job_id in sorted(os.listdir(day_path), reverse=True):
            job_json = day_path / job_id / "job.json"
            if not job_json.exists() or not _JOB_ID_RE.match(job_id):
                continue
            try:
                j = json.loads(job_json.read_text())
                jobs.append({
                    "date": day,
                    "job_id": job_id,
                    "id": j.get("id", job_id),
                    "workflow_id": j.get("workflow_id", ""),
                    "status": j.get("status", ""),
                    "request": (j.get("request") or "")[:200],
                })
            except Exception:
                pass
    return {"jobs": jobs[:200]}


@app.delete("/api/jobs/{date}/{job_id}")
def delete_job_api(date: str, job_id: str):
    """Delete a job directory. Returns 204 on success."""
    job_dir = _get_job_path(date, job_id)
    try:
        shutil.rmtree(job_dir)
    except OSError as e:
        raise HTTPException(status_code=500, detail=f"Delete failed: {e}")
    return Response(status_code=204)


@app.post("/api/jobs/{date}/{job_id}/delete")
def delete_job_form(date: str, job_id: str):
    """Delete a job (for HTML form POST). Redirects to /."""
    job_dir = _get_job_path(date, job_id)
    try:
        shutil.rmtree(job_dir)
    except OSError:
        raise HTTPException(status_code=500, detail="Delete failed")
    return RedirectResponse(url="/", status_code=303)


# ── Legacy: Job list (with delete) ───────────────────────────
@app.get("/", response_class=HTMLResponse)
def index():
    jobs = []
    if JOBS_PATH.exists():
        for day in sorted(os.listdir(JOBS_PATH), reverse=True)[:30]:
            day_path = JOBS_PATH / day
            if not day_path.is_dir():
                continue
            for job_id in sorted(os.listdir(day_path), reverse=True):
                job_json = day_path / job_id / "job.json"
                if job_json.exists():
                    try:
                        j = json.loads(job_json.read_text())
                        jobs.append({
                            "date": day,
                            "job_id": job_id,
                            "id": j.get("id", job_id),
                            "workflow_id": j.get("workflow_id", ""),
                            "status": j.get("status", ""),
                            "request": (j.get("request") or "")[:120],
                        })
                    except Exception:
                        pass
    # Build HTML with delete button per row (form POST for no-JS)
    rows = []
    for item in jobs[:100]:
        date_esc = item["date"].replace("&", "&amp;").replace("<", "&lt;")
        job_id_esc = item["job_id"].replace("&", "&amp;").replace("<", "&lt;")
        req_esc = (item["request"] or "").replace("&", "&amp;").replace("<", "&lt;")
        rows.append(
            f'<li style="margin:.4em 0">'
            f'<span>{item["id"]} | {item["workflow_id"]} | {item["status"]}'
            f' | <small>{req_esc}</small></span> '
            f'<form method="post" action="/api/jobs/{date_esc}/{job_id_esc}/delete" style="display:inline">'
            f'<button type="submit" name="delete" value="1">Löschen</button></form>'
            f'</li>'
        )
    return "<h1>Operator Dashboard</h1><p>Vergangene Jobs (Research u.a.) — Löschen möglich:</p><ul>" + "".join(rows) + "</ul>"


# ── Research API ────────────────────────────────────────────
@app.get("/api/research/projects")
def list_projects():
    """List all research projects with summary info."""
    projects = []
    if not RESEARCH.exists():
        return {"projects": []}
    for proj_dir in sorted(RESEARCH.iterdir(), reverse=True):
        if not proj_dir.is_dir() or not proj_dir.name.startswith("proj-"):
            continue
        pj = proj_dir / "project.json"
        if not pj.exists():
            continue
        d = _safe_json(pj)
        if not d:
            continue
        projects.append({
            "id": d.get("id", proj_dir.name),
            "question": (d.get("question", "") or "")[:200],
            "status": d.get("status", "unknown"),
            "phase": d.get("phase", "unknown"),
            "created_at": d.get("created_at", ""),
            "last_phase_at": d.get("last_phase_at", ""),
            "current_spend": d.get("current_spend", 0.0),
            "domain": d.get("domain", "general"),
        })
    return {"projects": projects}


@app.get("/api/research/projects/{project_id}")
def get_project(project_id: str):
    """Full project detail including gate metrics, budget, phase timings."""
    proj = _validate_project_id(project_id)
    d = _safe_json(proj / "project.json")
    read_stats = _safe_json(proj / "explore" / "read_stats.json")
    findings_count = len(list((proj / "findings").glob("*.json"))) if (proj / "findings").exists() else 0
    sources_count = len([f for f in (proj / "sources").glob("*.json") if not f.name.endswith("_content.json")]) if (proj / "sources").exists() else 0
    return {
        **d,
        "computed": {
            "findings_count": findings_count,
            "sources_count": sources_count,
            "read_stats": read_stats,
        },
    }


@app.get("/api/research/projects/{project_id}/sources")
def get_sources(project_id: str):
    """All sources with reliability scores and read status."""
    proj = _validate_project_id(project_id)
    sources_dir = proj / "sources"
    if not sources_dir.exists():
        return {"sources": []}
    reliability_map = {}
    rel_file = proj / "verify" / "source_reliability.json"
    if rel_file.exists():
        rel = _safe_json(rel_file)
        for s in rel.get("sources", []):
            url = (s.get("url") or "").strip()
            if url:
                reliability_map[url] = {
                    "reliability_score": s.get("reliability_score", 0.5),
                    "flags": s.get("flags", []),
                }
    sources = []
    for f in sorted(sources_dir.glob("*.json")):
        if f.name.endswith("_content.json"):
            continue
        s = _safe_json(f)
        if not s:
            continue
        src_id = f.stem
        url = (s.get("url") or "").strip()
        has_content = (sources_dir / f"{src_id}_content.json").exists()
        content_error = ""
        if has_content:
            content = _safe_json(sources_dir / f"{src_id}_content.json")
            content_error = content.get("error_code", "")
        rel_info = reliability_map.get(url, {})
        sources.append({
            "source_id": src_id,
            "url": url,
            "title": s.get("title", ""),
            "domain": url.split("/")[2] if url.startswith("http") and len(url.split("/")) > 2 else "",
            "read_attempted": has_content,
            "read_success": has_content and not content_error,
            "read_error": content_error,
            "reliability_score": rel_info.get("reliability_score"),
            "reliability_flags": rel_info.get("flags", []),
            "source_type": s.get("source", "unknown"),
        })
    return {"sources": sources, "total": len(sources)}


@app.get("/api/research/projects/{project_id}/claims")
def get_claims(project_id: str):
    """Claim ledger with evidence mapping."""
    proj = _validate_project_id(project_id)
    verify_dir = proj / "verify"
    ledger = _safe_json(verify_dir / "claim_ledger.json") if (verify_dir / "claim_ledger.json").exists() else {}
    evidence_map = _safe_json(verify_dir / "claim_evidence_map_latest.json") if (verify_dir / "claim_evidence_map_latest.json").exists() else {}
    evidence_by_id = {}
    for c in evidence_map.get("claims", []):
        cid = c.get("claim_id")
        if cid:
            evidence_by_id[cid] = c
    claims = []
    for c in ledger.get("claims", []):
        cid = c.get("claim_id", "")
        ev = evidence_by_id.get(cid, {})
        claims.append({
            **c,
            "evidence_excerpt": ev.get("evidence_excerpt", ""),
        })
    verified_count = sum(1 for c in claims if c.get("is_verified"))
    return {
        "claims": claims,
        "total": len(claims),
        "verified_count": verified_count,
        "support_rate": round(verified_count / len(claims), 3) if claims else 0.0,
    }


@app.get("/api/research/projects/{project_id}/report")
def get_report(project_id: str):
    """Latest report content + manifest."""
    proj = _validate_project_id(project_id)
    reports_dir = proj / "reports"
    if not reports_dir.exists():
        return {"report": None, "manifest": None}
    manifest = _safe_json(reports_dir / "manifest.json") if (reports_dir / "manifest.json").exists() else None
    reports = sorted(reports_dir.glob("report_*.md"), key=lambda p: p.stat().st_mtime, reverse=True)
    latest = None
    if reports:
        try:
            content = reports[0].read_text(encoding="utf-8", errors="replace")
            latest = {
                "filename": reports[0].name,
                "content": content,
                "size_bytes": len(content.encode("utf-8")),
            }
        except OSError:
            pass
    return {"report": latest, "manifest": manifest}


@app.get("/api/research/projects/{project_id}/audit")
def get_audit(project_id: str):
    """Audit log entries for the project."""
    proj = _validate_project_id(project_id)
    log_file = proj / "audit_log.jsonl"
    if not log_file.exists():
        return {"entries": [], "total": 0}
    entries = []
    try:
        for line in log_file.read_text().splitlines():
            line = line.strip()
            if line:
                try:
                    entries.append(json.loads(line))
                except json.JSONDecodeError:
                    pass
    except OSError:
        pass
    return {"entries": entries, "total": len(entries)}
