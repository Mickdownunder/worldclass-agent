#!/usr/bin/env python3
"""
Parallel URL reader for research: fetch multiple URLs with 3-5 workers, apply relevance gate, save to project.
Replaces sequential bash while-read loops in research-cycle.sh.

Usage:
  research_parallel_reader.py <project_id> <mode> --input-file <path> [--read-limit N] [--workers N]

  mode: explore | focus | counter | recovery
  input-file: path to file with one URL or one path-to-source-JSON per line
  read-limit: max URLs to read (default: mode-dependent)
  workers: 3-5 (default 4)
"""
import json
import os
import subprocess
import sys
import threading
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

OPERATOR_ROOT = Path(os.environ.get("OPERATOR_ROOT", Path(__file__).resolve().parent.parent))
TOOLS = OPERATOR_ROOT / "tools"


def _get_url_from_line(line: str, proj_dir: Path) -> str:
    """Resolve line to URL: if line is path to JSON file, load url; else treat line as URL."""
    line = (line or "").strip()
    if not line:
        return ""
    p = Path(line)
    if p.exists() and p.suffix == ".json":
        try:
            d = json.loads(p.read_text())
            return (d.get("url") or "").strip()
        except Exception:
            return ""
    if "://" in line:
        return line
    return ""


def _read_one_url(url: str, project_id: str) -> dict:
    """Run research_web_reader.py for one URL; return parsed JSON result."""
    env = os.environ.copy()
    env["RESEARCH_PROJECT_ID"] = project_id
    try:
        r = subprocess.run(
            [sys.executable, str(TOOLS / "research_web_reader.py"), url],
            capture_output=True,
            text=True,
            timeout=90,
            cwd=str(OPERATOR_ROOT),
            env=env,
        )
        if r.returncode == 0 and r.stdout:
            return json.loads(r.stdout)
    except (json.JSONDecodeError, subprocess.TimeoutExpired, Exception):
        pass
    return {"url": url, "title": "", "text": "", "error": "read_failed", "error_code": "parallel_read_error"}


def _save_result(
    proj_dir: Path,
    url: str,
    data: dict,
    question: str,
    mode: str,
    rel_threshold: float,
    source_label: str,
    lock: threading.Lock,
) -> bool:
    """Apply relevance gate and write content + finding to proj_dir. Returns True if saved (success + relevant)."""
    import hashlib
    text = (data.get("text") or data.get("abstract") or "")[:8000]
    title = data.get("title", "")
    relevant = True
    rel_score = 10.0
    if text and question:
        try:
            from tools.research_relevance_gate import check_relevance
            gate = check_relevance(question, title, text, project_id="")
            relevant = gate.get("relevant", True)
            rel_score = float(gate.get("score", 10))
            if not relevant:
                print(f"FILTERED (score={rel_score}): {url[:80]} — {gate.get('reason','')}", file=sys.stderr)
        except Exception as e:
            print(f"WARN: relevance gate error: {e}", file=sys.stderr)
    if relevant and rel_score < rel_threshold:
        relevant = False
        print(f"FILTERED (below threshold={rel_threshold:.2f}, score={rel_score}): {url[:80]}", file=sys.stderr)
    if not relevant:
        return False
    sid = hashlib.sha256(url.encode()).hexdigest()[:12]
    with lock:
        (proj_dir / "sources" / f"{sid}_content.json").write_text(json.dumps(data, ensure_ascii=False))
        if text:
            confidence = min(0.9, 0.4 + rel_score * 0.05) if mode != "counter" else min(0.8, 0.3 + rel_score * 0.05)
            fid = hashlib.sha256((url + text[:200]).encode()).hexdigest()[:12]
            (proj_dir / "findings" / f"{fid}.json").write_text(json.dumps({
                "url": url, "title": title, "excerpt": text[:4000], "source": source_label,
                "confidence": confidence, "relevance_score": rel_score,
            }, ensure_ascii=False))
    return True


def _run_worker(
    item: tuple[int, str],
    proj_dir: Path,
    question: str,
    project_id: str,
    mode: str,
    rel_threshold: float,
    source_label: str,
    lock: threading.Lock,
    results: list,
) -> None:
    idx, line = item
    url = _get_url_from_line(line, proj_dir)
    if not url:
        results.append((idx, -1, 0))  # skipped (not an attempt)
        return
    data = _read_one_url(url, project_id)
    text = (data.get("text") or data.get("abstract") or "").strip()
    err = (data.get("error") or "").strip()
    success = bool(text and not err)
    saved = False
    if success:
        saved = _save_result(proj_dir, url, data, question, mode, rel_threshold, source_label, lock)
    results.append((idx, 1 if success else 0, 1 if saved else 0))


def main() -> None:
    if len(sys.argv) < 5 or "--input-file" not in sys.argv:
        print("Usage: research_parallel_reader.py <project_id> <mode> --input-file <path> [--read-limit N] [--workers N]", file=sys.stderr)
        sys.exit(2)
    project_id = sys.argv[1]
    mode = sys.argv[2].lower()
    if mode not in ("explore", "focus", "counter", "recovery"):
        print("mode must be explore|focus|counter|recovery", file=sys.stderr)
        sys.exit(2)
    idx = sys.argv.index("--input-file") + 1
    input_file = Path(sys.argv[idx])
    if not input_file.exists():
        print(json.dumps({"read_attempts": 0, "read_successes": 0, "read_failures": 0}))
        return
    read_limit = 40
    if "--read-limit" in sys.argv:
        midx = sys.argv.index("--read-limit") + 1
        if midx < len(sys.argv):
            read_limit = max(1, int(sys.argv[midx]))
    if mode == "focus":
        read_limit = min(read_limit, 15)
    elif mode == "counter":
        read_limit = min(read_limit, 9)
    elif mode == "recovery":
        read_limit = min(read_limit, 10)
    workers = 4
    if "--workers" in sys.argv:
        widx = sys.argv.index("--workers") + 1
        if widx < len(sys.argv):
            workers = max(1, min(5, int(sys.argv[widx])))
    workers = min(workers, read_limit)

    from tools.research_common import project_dir
    proj_dir = project_dir(project_id)
    if not proj_dir.exists():
        print(json.dumps({"read_attempts": 0, "read_successes": 0, "read_failures": 0}))
        return
    project = {}
    try:
        project = json.loads((proj_dir / "project.json").read_text())
    except Exception:
        pass
    question = (project.get("question") or "").strip()
    rel_threshold = float(os.environ.get("RESEARCH_MEMORY_RELEVANCE_THRESHOLD", "0.50"))
    source_label = "read" if mode != "counter" else "counter_read"

    lines = [ln.strip() for ln in input_file.read_text().splitlines() if ln.strip()][:read_limit]
    if not lines:
        print(json.dumps({"read_attempts": 0, "read_successes": 0, "read_failures": 0}))
        return

    lock = threading.Lock()
    results: list[tuple[int, int, int]] = []
    try:
        from tools.research_progress import step as progress_step
    except Exception:
        progress_step = lambda _pid, _msg, _cur, _tot: None

    from concurrent.futures import ThreadPoolExecutor, as_completed
    total = len(lines)
    attempts = 0
    successes = 0
    saved_count = 0
    with ThreadPoolExecutor(max_workers=workers) as executor:
        futures = {executor.submit(
            _run_worker,
            (i, line),
            proj_dir,
            question,
            project_id,
            mode,
            rel_threshold,
            source_label,
            lock,
            results,
        ): i for i, line in enumerate(lines)}
        completed = 0
        for future in as_completed(futures):
            try:
                future.result()
                completed += 1
                progress_step(project_id, f"Reading source {completed}/{total}", completed, total)
            except Exception as e:
                print(f"WARN: parallel read worker failed: {e}", file=sys.stderr)
    # Results list is appended by workers; sort by idx and aggregate
    results.sort(key=lambda x: x[0])
    for _idx, succ, saved in results:
        if succ >= 0:  # valid URL was attempted
            attempts += 1
            if succ:
                successes += 1
        if saved:
            saved_count += 1
    out = {"read_attempts": attempts, "read_successes": successes, "read_failures": attempts - successes}
    print(json.dumps(out))


if __name__ == "__main__":
    main()
