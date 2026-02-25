from fastapi import FastAPI
from fastapi.responses import HTMLResponse
import os
import json

app = FastAPI()

JOBS_PATH = "/root/operator/jobs"

@app.get("/", response_class=HTMLResponse)
def index():
    rows = []
    if os.path.exists(JOBS_PATH):
        for day in sorted(os.listdir(JOBS_PATH), reverse=True):
            day_path = os.path.join(JOBS_PATH, day)
            for job in os.listdir(day_path):
                job_json = os.path.join(day_path, job, "job.json")
                if os.path.exists(job_json):
                    try:
                        with open(job_json) as f:
                            j = json.load(f)
                            rows.append(f"<li>{j['id']} | {j['workflow_id']} | {j['status']}</li>")
                    except:
                        pass

    return "<h1>Operator Dashboard</h1><ul>" + "".join(rows) + "</ul>"
