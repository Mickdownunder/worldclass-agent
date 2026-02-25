#!/usr/bin/env python3
"""
Shared helpers for research tools: paths, secrets, project layout.
"""
import os
import json
from pathlib import Path

def operator_root() -> Path:
    return Path(os.environ.get("OPERATOR_ROOT", Path.home() / "operator"))

def research_root() -> Path:
    return operator_root() / "research"

def project_dir(project_id: str) -> Path:
    return research_root() / project_id

def load_secrets() -> dict:
    secrets = {}
    conf = operator_root() / "conf" / "secrets.env"
    if conf.exists():
        for line in conf.read_text().splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, v = line.split("=", 1)
                secrets[k.strip()] = v.strip()
    for k, v in os.environ.items():
        if k.startswith("OPENAI_") or k in ("BRAVE_API_KEY", "SERPER_API_KEY"):
            secrets[k] = v
    return secrets

def ensure_project_layout(proj_path: Path) -> None:
    (proj_path / "findings").mkdir(parents=True, exist_ok=True)
    (proj_path / "sources").mkdir(parents=True, exist_ok=True)
    (proj_path / "reports").mkdir(parents=True, exist_ok=True)

def load_project(proj_path: Path) -> dict:
    pj = proj_path / "project.json"
    if not pj.exists():
        return {}
    return json.loads(pj.read_text())

def save_project(proj_path: Path, data: dict) -> None:
    (proj_path / "project.json").write_text(json.dumps(data, indent=2) + "\n")
