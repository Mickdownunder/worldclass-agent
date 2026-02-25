#!/usr/bin/env python3
import json, sys
from datetime import datetime, timezone
from pathlib import Path
import csv

def ensure_dir(p: Path):
    p.mkdir(parents=True, exist_ok=True)

def md_escape(s: str) -> str:
    return (s or "").replace("\r", "").strip()

def main():
    if len(sys.argv) != 4:
        print("usage: opportunity_pack_build.py <client_id> <match_map.json> <packs_root>", file=sys.stderr)
        return 2

    client_id, map_path, packs_root = sys.argv[1], Path(sys.argv[2]), Path(sys.argv[3])

    m = json.loads(map_path.read_text(encoding="utf-8"))
    if client_id not in m["clients"]:
        print(f"client_id not found: {client_id}", file=sys.stderr)
        return 1

    data = m["clients"][client_id]
    client = data["client"]
    matches = data["matches"]

    if not matches:
        print("no matches; nothing to build")
        return 3

    stamp = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    pack_dir = packs_root / client_id / stamp
    ensure_dir(pack_dir)
    ensure_dir(pack_dir / "outreach")

    lines = []
    lines.append(f"# Opportunity Pack — {client.get('name')} — {stamp}")
    lines.append("")
    lines.append(f"Items: {len(matches)}  | min_score: {client.get('min_score')}")
    lines.append("")
    for i, opp in enumerate(matches, 1):
        lines.append(f"## {i}. {md_escape(opp.get('title'))} (score {opp.get('score'):.2f})")
        lines.append("")
        if opp.get("topics"):
            lines.append(f"Topics: {', '.join(opp['topics'])}")
            lines.append("")
        if opp.get("summary"):
            lines.append(md_escape(opp["summary"]))
            lines.append("")
        if opp.get("evidence"):
            lines.append("Evidence:")
            for ev in opp["evidence"]:
                lines.append(f"- {ev}")
            lines.append("")
    (pack_dir / "summary.md").write_text("\n".join(lines), encoding="utf-8")

    with open(pack_dir / "opportunities.csv", "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["id","title","score","topics","source","evidence_1","evidence_2","evidence_3"])
        w.writeheader()
        for opp in matches:
            ev = (opp.get("evidence") or []) + ["","",""]
            w.writerow({
                "id": opp.get("id",""),
                "title": opp.get("title",""),
                "score": opp.get("score",0),
                "topics": ",".join(opp.get("topics") or []),
                "source": opp.get("source",""),
                "evidence_1": ev[0],
                "evidence_2": ev[1],
                "evidence_3": ev[2]
            })

    for i, opp in enumerate(matches, 1):
        outreach = []
        outreach.append(f"# Outreach Draft {i}: {md_escape(opp.get('title'))}")
        outreach.append("")
        outreach.append("## Email (draft)")
        outreach.append("")
        outreach.append(f"Subject: Quick question re: {md_escape(opp.get('title'))[:60]}")
        outreach.append("")
        outreach.append("Hi {{name}},")
        outreach.append("")
        outreach.append(f"I noticed: {md_escape(opp.get('summary'))}")
        outreach.append("")
        outreach.append("If this is on your radar, I can share a short, concrete approach.")
        outreach.append("")
        outreach.append("Worth a 10-min chat this week?")
        outreach.append("")
        outreach.append("— Mike")
        (pack_dir / "outreach" / f"{i:02d}_{opp.get('id','opp')}.md").write_text("\n".join(outreach), encoding="utf-8")

    meta = {
        "client_id": client_id,
        "client_name": client.get("name"),
        "generated_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "items": len(matches),
        "pack_dir": str(pack_dir)
    }
    (pack_dir / "pack.json").write_text(json.dumps(meta, indent=2), encoding="utf-8")

    print(str(pack_dir))
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
