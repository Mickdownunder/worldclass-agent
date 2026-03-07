"""Checkpoint load/save/clear for resume-after-interrupt."""
import json
from pathlib import Path

from tools.synthesis.constants import SYNTHESIZE_CHECKPOINT


def _load_checkpoint(proj_path: Path) -> dict | None:
    p = proj_path / SYNTHESIZE_CHECKPOINT
    if not p.exists():
        return None
    try:
        data = json.loads(p.read_text())
        if not isinstance(data.get("clusters"), list) or not isinstance(data.get("section_titles"), list) or not isinstance(data.get("bodies"), list):
            return None
        return data
    except Exception:
        return None


def _save_checkpoint(proj_path: Path, clusters: list, section_titles: list, bodies: list) -> None:
    p = proj_path / SYNTHESIZE_CHECKPOINT
    try:
        p.write_text(json.dumps({"clusters": clusters, "section_titles": section_titles, "bodies": bodies}, indent=2, ensure_ascii=False))
    except Exception:
        pass


def _clear_checkpoint(proj_path: Path) -> None:
    (proj_path / SYNTHESIZE_CHECKPOINT).unlink(missing_ok=True)
