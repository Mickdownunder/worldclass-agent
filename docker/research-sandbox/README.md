# Research Sandbox Image

Python 3.11 + **numpy** + **scipy** for the Experiment Loop. No network at runtime.

**Build (once):**
```bash
# from operator root
docker build -t operator-research-sandbox:latest -f docker/research-sandbox/Dockerfile docker/research-sandbox/
```

If the image is not built, the sandbox falls back to `python:3.11-slim` (stdlib only).

Override image: `RESEARCH_SANDBOX_IMAGE=myimage:tag`
