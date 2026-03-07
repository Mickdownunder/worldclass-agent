"""Query embedding for hybrid semantic retrieval. Used by retrieve_with_utility."""
import os
from pathlib import Path

EMBEDDING_MODEL = "text-embedding-3-small"
EMBEDDING_DIM = 1536


def embed_query(text: str) -> list[float] | None:
    """Return query embedding vector or None if disabled/failed. Used for hybrid semantic retrieval."""
    if not (text or "").strip() or os.environ.get("RESEARCH_MEMORY_SEMANTIC", "1") == "0":
        return None
    try:
        api_key = os.environ.get("OPENAI_API_KEY")
        if not api_key:
            root = Path(os.environ.get("OPERATOR_ROOT", str(Path.home() / "operator")))
            conf = root / "conf" / "secrets.env"
            if conf.exists():
                for line in conf.read_text().splitlines():
                    line = line.strip()
                    if line.startswith("OPENAI_API_KEY=") and "=" in line:
                        api_key = line.split("=", 1)[1].strip().strip('"\'')
                        break
        if not api_key:
            return None
        from openai import OpenAI
        client = OpenAI(api_key=api_key)
        r = client.embeddings.create(input=(text or "")[:8000], model=EMBEDDING_MODEL)
        if r.data and len(r.data) > 0:
            return list(r.data[0].embedding)
    except Exception:
        pass
    return None
