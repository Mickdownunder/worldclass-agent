#!/usr/bin/env python3
"""One-off: read MASTER_DOSSIER.md, extract Mega-Principles section, inject into Memory.
Usage: python3 inject_council_principles_from_dossier.py <parent_project_id>
"""
import re
import sys
from pathlib import Path

OPERATOR_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(OPERATOR_ROOT))
RESEARCH = OPERATOR_ROOT / "research"


def extract_principles(md_path: Path) -> list[str]:
    content = md_path.read_text(encoding="utf-8")
    principles = []
    in_section = False
    for line in content.split("\n"):
        if "## Mega-Principles" in line or "## Mega Principles" in line:
            in_section = True
            continue
        if in_section:
            if line.strip().startswith("## ") and "Mega" not in line:
                break
            stripped = line.strip()
            if re.match(r"^[123]\.\s+\*\*", stripped):
                # "1.  **Title:** Description..." -> remove leading "N.  "
                rest = re.sub(r"^[123]\.\s+", "", stripped)
                if rest:
                    principles.append(rest)
    return principles


def main():
    if len(sys.argv) < 2:
        print("Usage: inject_council_principles_from_dossier.py <parent_project_id>", file=sys.stderr)
        sys.exit(2)
    parent_id = sys.argv[1].strip()
    parent_dir = RESEARCH / parent_id
    if not parent_dir.is_dir():
        print(f"Project not found: {parent_id}", file=sys.stderr)
        sys.exit(1)
    dossier = parent_dir / "MASTER_DOSSIER.md"
    if not dossier.exists():
        print(f"MASTER_DOSSIER.md not found in {parent_id}", file=sys.stderr)
        sys.exit(1)
    principles = extract_principles(dossier)
    if not principles:
        print("No principles extracted from Mega-Principles section.", file=sys.stderr)
        sys.exit(1)
    from lib.memory import Memory
    import json
    mem = Memory()
    domain = "general"
    try:
        p_json = json.loads((parent_dir / "project.json").read_text())
        domain = p_json.get("domain", "general")
    except Exception:
        pass
    evidence_json = json.dumps(["Derived from MASTER_DOSSIER (council synthesis)."])
    for desc in principles:
        mem.insert_principle(
            principle_type="council_synthesis",
            description=desc[:2000],
            source_project_id=parent_id,
            domain=domain,
            evidence_json=evidence_json,
            metric_score=0.9,
        )
    mem.close()
    print(f"Injected {len(principles)} principles into Brain.")
    result_path = parent_dir / "council_result.json"
    result = {"brain_injected": True, "brain_error": None}
    try:
        result_path.write_text(json.dumps(result, indent=2), encoding="utf-8")
    except Exception:
        pass
    print("Updated council_result.json (brain_injected=true).")


if __name__ == "__main__":
    main()
