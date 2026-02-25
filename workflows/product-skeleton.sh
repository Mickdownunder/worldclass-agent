#!/usr/bin/env bash
set -e

ART="$PWD/artifacts"
mkdir -p "$ART"

BASE="/root/operator/sandbox/products/operator-dashboard"
mkdir -p "$BASE/templates"

# --- basic app ---
cat > "$BASE/app.py" <<'EOF'
from fastapi import FastAPI
from fastapi.responses import HTMLResponse
import os

app = FastAPI()

@app.get("/", response_class=HTMLResponse)
def index():
    jobs_path = "/root/operator/jobs"
    jobs = []
    if os.path.exists(jobs_path):
        for d in sorted(os.listdir(jobs_path)):
            jobs.append(d)
    return f"<h1>Operator Dashboard</h1><p>Job dates: {jobs}</p>"
EOF

# --- requirements ---
cat > "$BASE/requirements.txt" <<'EOF'
fastapi
uvicorn
EOF

# --- run script ---
cat > "$BASE/run.sh" <<'EOF'
#!/usr/bin/env bash
uvicorn app:app --host 0.0.0.0 --port 8090
EOF
chmod +x "$BASE/run.sh"

# --- readme ---
cat > "$BASE/README.md" <<'EOF'
# Operator Dashboard

Minimal dashboard skeleton.

Run:
pip install -r requirements.txt
./run.sh
EOF

cat > "$ART/product-skeleton.md" <<EOF
# Product Skeleton Created

Product: operator-dashboard
Location: $BASE
EOF
