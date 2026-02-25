import os, subprocess
from openai import OpenAI

ctx = subprocess.check_output(
    ["/root/operator/tools/opportunity-context.sh"]
).decode().strip().split()[-1]

with open(ctx) as f:
    state = f.read()

prompt = f"""
You are an operator factory strategist.

Given this operator state, propose 5 high-leverage capability opportunities.

Return JSON list:
[{{"name":"","type":"tool|product|workflow","reason":""}}]

STATE:
{state}
"""

client = OpenAI()

resp = client.responses.create(
    model="gpt-4.1-mini",
    input=prompt
)

print(resp.output_text)
