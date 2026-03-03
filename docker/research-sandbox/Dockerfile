# Research Sandbox: Python + numpy + scipy for report experiments.
# No network at runtime; used by research_sandbox.py.
FROM python:3.11-slim

RUN pip install --no-cache-dir numpy scipy

WORKDIR /app
# No USER switch so we keep same as base (root in container, harmless when --network none)
CMD ["python", "script.py"]
