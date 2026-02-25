#!/usr/bin/env bash
set -e

ART="$PWD/artifacts"
mkdir -p "$ART"

QUEUE=$(find /root/operator/jobs -name queue.json -printf "%T@ %p\n" | sort -n | tail -n 1 | cut -d' ' -f2- || true)

if [ -z "$QUEUE" ] || [ ! -f "$QUEUE" ]; then
  echo "No queue" > "$ART/telegram.txt"
  exit 0
fi

export QUEUE

python3 - <<PY
import json, os

q=os.environ["QUEUE"]
with open(q) as f:
    data=json.load(f)

jobs=data.get("jobs",[])
msg=["Factory queue ready:\n"]

for i,j in enumerate(jobs,1):
    msg.append(f"{i}. {j['name']} ({j['workflow']})")

msg.append("\nCommands:")
msg.append("/qrun 1")
msg.append("/qrunall")
msg.append("/skip")

out="\n".join(msg)

with open(os.environ["PWD"]+"/artifacts/telegram.txt","w") as f:
    f.write(out)

print(out)
PY
