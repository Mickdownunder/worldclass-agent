#!/usr/bin/env bash
set -e

ART="$PWD/artifacts"
mkdir -p "$ART"

########################################
# Header
########################################

echo "# Opportunity Discovery" > "$ART/opportunities.md"
date >> "$ART/opportunities.md"

echo "" >> "$ART/opportunities.md"
echo "## Heuristic Signals" >> "$ART/opportunities.md"

########################################
# LLM opportunity generation
########################################

echo "" >> "$ART/opportunities.md"
echo "## LLM Opportunities" >> "$ART/opportunities.md"

# Run LLM generator (FAIL HARD if broken)
/root/operator/tools/opportunity-llm.sh > "$ART/llm.json"

# Append readable view
cat "$ART/llm.json" >> "$ART/opportunities.md"

########################################
# Heuristic signals
########################################

jobs_count=$(find /root/operator/jobs -name job.json | wc -l)
echo "" >> "$ART/opportunities.md"
echo "- Total jobs observed: $jobs_count" >> "$ART/opportunities.md"

########################################
# Static candidate seeds
########################################

echo "" >> "$ART/opportunities.md"
echo "## Candidate Opportunities" >> "$ART/opportunities.md"

echo "- Summarization tool for job logs" >> "$ART/opportunities.md"
echo "- Artifact browser tool" >> "$ART/opportunities.md"
echo "- Job failure clustering tool" >> "$ART/opportunities.md"

########################################
# Machine-readable summary
########################################

cat > "$ART/opportunities.json" <<JSON
{
  "ts": "$(date -u +"%Y-%m-%dT%H:%M:%SZ")",
  "candidates": [
    {"type":"tool","name":"job-log-summarizer"},
    {"type":"tool","name":"artifact-browser"},
    {"type":"tool","name":"failure-cluster"}
  ]
}
JSON

########################################
# Feed tool backlog
########################################

/root/operator/bin/op job new --workflow tool-backlog-add --request "opportunity discovery feed" \
  | xargs -I{} /root/operator/bin/op run {} >> "$PWD/log.txt" 2>&1

########################################
# Commit knowledge
########################################

/root/operator/bin/op job new --workflow knowledge-commit --request "opportunity discovery commit" \
  | xargs -I{} /root/operator/bin/op run {} >> "$PWD/log.txt" 2>&1
