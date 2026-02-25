# Research System

Autonomous multi-day research projects. Each project lives under `research/<project_id>/`.

## Layout (per project)

```
<project_id>/
  project.json     # question, status, created_at, domain, config
  findings/        # one JSON file per finding (id.json)
  sources/         # cached source content (by URL hash or id)
  reports/         # intermediate and final reports
  questions.json   # open questions (evolving)
  thesis.json      # current hypothesis (evolving)
```

## Workflows

- **research-init** — Create a new project from a research question (sets phase=explore).
- **research-search** — Run web + academic search for a project; append to sources.
- **research-read** — Fetch and extract content from URLs/PDFs; save to sources/findings.
- **research-synthesize** — Combine findings, produce report draft.
- **research-cycle** — Run one phase of the cycle (explore→focus→connect→verify→synthesize→done). Call repeatedly for multi-day research.
- **research-cross-domain** — Index all findings with embeddings; find high-similarity pairs across projects; optionally notify.

## Feedback

- **Telegram:** `/research-feedback <project_id> <dig_deeper|wrong|excellent|ignore> [comment]` or `redirect "new question"`.
- **UI:** `POST /api/research/feedback` with body `{ project_id, type, comment? }`. Feedback is appended to `research/<id>/feedback.jsonl`. Use type `redirect` to add a new question and set phase back to focus.

## Usage (via job engine)

```bash
# Create project
op job new --workflow research-init --request "What is the market size for vertical SaaS in EU?"
op run <job_id>
# → artifacts/project_id.txt contains the new project id

# Search (use project id from above)
op job new --workflow research-search --request "proj-<id>"
op run <job_id>

# Read a specific URL (project_id and url in request)
op job new --workflow research-read --request "proj-<id> https://example.com/page"
op run <job_id>

# Synthesize
op job new --workflow research-synthesize --request "proj-<id>"
op run <job_id>
```

## Dependencies (optional)

- `pip install beautifulsoup4 pypdf` for web reader and PDF extraction.
- `BRAVE_API_KEY` or `SERPER_API_KEY` in `conf/secrets.env` for web search.
