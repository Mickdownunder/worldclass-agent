#!/usr/bin/env bash
set -e

ART="$PWD/artifacts"
mkdir -p "$ART"

MODE="${RUN_MODE:-all}"
IDX="${RUN_INDEX:-}"

QUEUE=$(find /root/operator/jobs -name queue.json -printf "%T@ %p\n" | sort -n | tail -n 1 | cut -d' ' -f2- || true)
if [ -z "$QUEUE" ] || [ ! -f "$QUEUE" ]; then
  echo "No queue.json found" > "$ART/ran.md"
  cat > "$ART/ran.json" <<JSON
{"error":"no_queue","results":[]}
JSON
  exit 0
fi

export QUEUE MODE IDX

python3 - <<'PY'
import json, os, subprocess, datetime, pathlib

q=os.environ["QUEUE"]
mode=os.environ["MODE"]
idx=os.environ.get("IDX","").strip()

with open(q) as f:
    jobs=json.load(f).get("jobs",[])

def run_job(job_dir: str):
    p = subprocess.run(["/root/operator/bin/op","run",job_dir], capture_output=True, text=True)
    status = (p.stdout or "").strip() or ("FAILED" if p.returncode != 0 else "DONE")
    # also read job.json status if present
    jobp = pathlib.Path(job_dir)/"job.json"
    if jobp.exists():
        try:
            j = json.loads(jobp.read_text())
            status = j.get("status", status)
        except:
            pass
    return {"job_dir": job_dir, "status": status, "rc": p.returncode}

selected=[]
if mode=="all":
    selected = jobs
elif idx:
    i=int(idx)-1
    if 0<=i<len(jobs):
        selected=[jobs[i]]

results=[]
for j in selected:
    results.append({
        "type": j.get("type"),
        "name": j.get("name"),
        "workflow": j.get("workflow"),
        **run_job(j["job_dir"])
    })

ts=datetime.datetime.utcnow().isoformat()+"Z"

out_json={"ts":ts,"source_queue":q,"mode":mode,"index":idx or None,"results":results}
open(os.path.join(os.environ["PWD"],"artifacts","ran.json"),"w").write(json.dumps(out_json, indent=2))

lines=[f"Queue run result ({ts})", ""]
for r in results:
    lines.append(f"- {r['status']} :: {r['workflow']} :: {r['name']} -> {r['job_dir']}")
lines.append("")
lines.append("Artifacts: use /job-artifacts <job_id> (IDs are last path segment).")

open(os.path.join(os.environ["PWD"],"artifacts","ran.md"),"w").write("\n".join(lines))

print("\n".join(lines))
PY
