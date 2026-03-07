# Plumber — Self-Healing Subsystem. Public API re-exports.
from __future__ import annotations

from .fingerprints import (
    _load_fingerprints,
    classify_non_repairable,
    get_fingerprint_stats,
)
from .fix import list_patches, rollback_patch
from .run import run_plumber

__all__ = [
    "run_plumber",
    "rollback_patch",
    "list_patches",
    "get_fingerprint_stats",
    "_load_fingerprints",
    "classify_non_repairable",
]
