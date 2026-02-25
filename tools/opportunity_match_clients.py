#!/usr/bin/env python3
import json, os, sys, glob
from datetime import datetime, timezone

def load_json(path):
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)

def iter_jsonl(path):
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            yield json.loads(line)

def topic_fit(opp_topics, client_topics, exclude_topics):
    opp_set = set(t.lower() for t in (opp_topics or []))
    client_set = set(t.lower() for t in (client_topics or []))
    excl_set = set(t.lower() for t in (exclude_topics or []))
    if opp_set & excl_set:
        return False
    return bool(opp_set & client_set)

def main():
    if len(sys.argv) != 4:
        print("usage: opportunity_match_clients.py <clients_dir> <opportunities.jsonl> <out_map.json>", file=sys.stderr)
        return 2

    clients_dir, opp_path, out_path = sys.argv[1], sys.argv[2], sys.argv[3]
    client_files = sorted(glob.glob(os.path.join(clients_dir, "*.json")))
    if not client_files:
        print(f"no clients in {clients_dir}", file=sys.stderr)
        return 1

    clients = [load_json(p) for p in client_files]

    out = {
        "generated_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "clients": {}
    }

    for c in clients:
        out["clients"][c["id"]] = {"client": c, "matches": []}

    for opp in iter_jsonl(opp_path):
        score = float(opp.get("score", 0.0))
        opp_topics = opp.get("topics", [])
        for c in clients:
            if score < float(c.get("min_score", 1.0)):
                continue
            if not topic_fit(opp_topics, c.get("topics", []), c.get("exclude_topics", [])):
                continue
            out["clients"][c["id"]]["matches"].append({
                "id": opp.get("id"),
                "title": opp.get("title"),
                "score": score,
                "topics": opp_topics,
                "summary": opp.get("summary", ""),
                "evidence": opp.get("evidence", [])[:5],
                "source": opp.get("source", "")
            })

    for cid, data in out["clients"].items():
        c = data["client"]
        max_items = int(c.get("max_items_per_pack", 20))
        data["matches"].sort(key=lambda x: x.get("score", 0), reverse=True)
        data["matches"] = data["matches"][:max_items]

    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=2)

    any_matches = any(len(d["matches"]) > 0 for d in out["clients"].values())
    print(f"wrote {out_path}. any_matches={any_matches}")
    return 0 if any_matches else 3

if __name__ == "__main__":
    raise SystemExit(main())
