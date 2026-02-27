#!/usr/bin/env bash
set -e

ART="$PWD/artifacts"
mkdir -p "$ART"

# find latest selected.json by mtime
SEL=$(find /root/operator/jobs -name selected.json -printf "%T@ %p\n" | sort -n | tail -n 1 | cut -d' ' -f2- || true)
export SEL

if [ -z "$SEL" ] || [ ! -f "$SEL" ]; then
  echo "No selected.json found" > "$ART/queue.md"
  cat > "$ART/queue.json" <<JSON
{"jobs":[],"error":"no_selected"}
JSON
  exit 0
fi

cat > "$ART/queue.md" <<MD
# Opportunity Dispatch Queue
Source: $SEL
MD

python3 - <<PY
import json, os, subprocess, shlex, datetime

sel_path = os.environ.get("SEL", "").strip()
if not sel_path or not os.path.isfile(sel_path):
    # Fallback: find latest selected.json
    base = "/root/operator/jobs"
    best = None
    best_mtime = 0
    for root, dirs, files in os.walk(base):
        for f in files:
            if f == "selected.json":
                path = os.path.join(root, f)
                try:
                    m = os.path.getmtime(path)
                    if m > best_mtime:
                        best_mtime = m
                        best = path
                except OSError:
                    pass
    sel_path = best or ""
if not sel_path:
    raise SystemExit("SEL not set and no selected.json found under /root/operator/jobs")
out_json = os.path.join(os.environ["PWD"],"artifacts","queue.json")
out_md   = os.path.join(os.environ["PWD"],"artifacts","queue.md")

with open(sel_path,"r",encoding="utf-8") as f:
    data=json.load(f)

items=data.get("selected",[])
jobs=[]

def op_job_new(workflow, request):
    p=subprocess.check_output(
        ["/root/operator/bin/op","job","new","--workflow",workflow,"--request",request],
        text=True
    ).strip()
    return p

for it in items:
    t=it.get("type","").strip()
    name=it.get("name","").strip()
    reason=it.get("reason","").strip()

    if not name:
        continue

    if t == "tool":
        wf="tool-idea"
        req=f"{name} :: {reason}"
    elif t == "product":
        wf="product-spec"
        req=f"{name} :: {reason}"
    elif t == "workflow":
        wf="tool-backlog-add"
        req=f"WORKFLOW_OPPORTUNITY :: {name} :: {reason}"
    else:
        wf="tool-backlog-add"
        req=f"UNKNOWN_OPPORTUNITY({t}) :: {name} :: {reason}"

    job_dir = op_job_new(wf, req)
    jobs.append({"type":t,"name":name,"workflow":wf,"job_dir":job_dir})

with open(out_json,"w",encoding="utf-8") as f:
    json.dump({"source":sel_path,"created_at":datetime.datetime.now(datetime.timezone.utc).isoformat()+"Z","jobs":jobs}, f, indent=2)

with open(out_md,"a",encoding="utf-8") as f:
    f.write("\n\n## Created Jobs\n")
    for j in jobs:
        f.write(f"- ({j['workflow']}) {j['name']} -> {j['job_dir']}\n")

print(f"created_jobs={len(jobs)}")
PY
