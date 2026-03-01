#!/usr/bin/env python3
"""
Offline memory consolidation job (wake-sleep style).

What it does:
- Build/update empirical strategy profiles from run_episodes per domain.
- Synthesize conservative guiding/cautionary principles from repeated what_helped/what_hurt signals.
- Run Auto-Prompt Optimization: mutate and test system prompts to find the best instructions.
- Emit a summary JSON for observability.

Usage:
  memory_consolidate.py [--min-samples 3] [--min-principle-count 3]
"""
from __future__ import annotations

import json
import sys
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from tools.research_common import llm_call, model_for_lane

def run_auto_prompt_optimization(domain: str, mem) -> dict | None:
    """
    Phase 4: Auto-Prompt Optimization.
    Finds the best prompt for the domain by generating variants and evaluating them against a fixed Baseline-Test.
    """
    conn = mem._conn
    # Get a successful recent episode in this domain to use as a seed for prompt generation
    row = conn.execute(
        "SELECT question, what_helped_json FROM run_episodes WHERE domain = ? AND status = 'done' AND critic_score >= 0.7 ORDER BY created_at DESC LIMIT 1",
        (domain,)
    ).fetchone()
    
    if not row:
        return None
        
    seed_question = row["question"]
    what_helped = row["what_helped_json"]
    
    print(f"[Auto-Prompt] Optimizing for domain: {domain}...")
    
    mid_model = model_for_lane("mid")
    strong_model = model_for_lane("critic")
    if "gpt" not in strong_model and "gemini" not in strong_model:
        strong_model = "gpt-5.2"
        
    sys_proj_id = "proj-sys-consolidate"
    from tools.research_common import project_dir, save_project
    pdir = project_dir(sys_proj_id)
    if not pdir.exists():
        pdir.mkdir(parents=True, exist_ok=True)
        save_project(pdir, {"id": sys_proj_id, "type": "system_job", "current_spend": 0.0})
        
    # 1. Generate Prompt Variations
    sys_gen = "You are an expert AI Prompt Engineer. Generate 3 distinct system prompt instructions (max 2 sentences each) to instruct a researcher AI on how to best answer questions in this domain. Make one highly analytical, one creative/lateral, and one strict/factual."
    user_gen = f"Domain: {domain}\nRecent successful traits: {what_helped}\nReturn ONLY a JSON array of 3 strings."
    
    try:
        variants_res = llm_call(mid_model, sys_gen, user_gen, project_id=sys_proj_id)
        text = variants_res.text.strip()
        if text.startswith("```json"): text = text[7:]
        if text.endswith("```"): text = text[:-3]
        variants = json.loads(text)
        if not isinstance(variants, list) or len(variants) < 3:
            return None
    except Exception as e:
        print(f"[Auto-Prompt] Generation failed: {e}")
        return None
        
    # Load Baseline Tasks (Task Set A)
    tasks_file = ROOT / "conf" / "prompt_eval_tasks.json"
    eval_tasks = [{"question": seed_question}] # Fallback
    if tasks_file.exists():
        try:
            all_tasks = json.loads(tasks_file.read_text())
            eval_tasks = [t for t in all_tasks if t.get("domain") == domain or t.get("domain") == "general"]
            if not eval_tasks:
                eval_tasks = all_tasks[:3]
        except Exception:
            pass
            
    # 2. A/B Test the variants against the Baseline
    best_score = -1.0
    best_prompt = ""
    
    eval_sys = "You are a harsh critic. Rate the AI's answer to the question on a scale of 0.0 to 1.0 based on depth, accuracy, and clarity. Return ONLY the float number."
    
    for prompt in variants[:3]:
        total_score = 0.0
        valid_tasks = 0
        for task in eval_tasks:
            q = task.get("question", "")
            if not q: continue
            
            # Simulate a quick generation
            sim_res = llm_call(mid_model, prompt, q, project_id=sys_proj_id)
            answer = sim_res.text
            
            # Evaluate
            eval_res = llm_call(strong_model, eval_sys, f"Question: {q}\nAnswer:\n{answer}", project_id=sys_proj_id)
            try:
                score = float(eval_res.text.strip())
            except:
                score = 0.5
                
            total_score += score
            valid_tasks += 1
            
        avg_score = total_score / max(1, valid_tasks)
            
        if avg_score > best_score:
            best_score = avg_score
            best_prompt = prompt

    # 3. Store the winner in versioned ledger
    if best_prompt and best_score >= 0.7:
        import uuid
        from datetime import datetime, timezone
        
        versions_file = ROOT / "memory" / "prompt_versions.json"
        versions = []
        if versions_file.exists():
            try:
                versions = json.loads(versions_file.read_text())
            except Exception:
                pass
                
        # Archive older active prompts for this domain
        for v in versions:
            if v.get("domain") == domain and v.get("status") == "active":
                v["status"] = "archived"
                
        new_version = {
            "id": str(uuid.uuid4()),
            "domain": domain,
            "prompt_text": best_prompt,
            "avg_score": round(best_score, 3),
            "created_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "status": "active"
        }
        versions.append(new_version)
        versions_file.write_text(json.dumps(versions, indent=2))
        
        return {"winner": best_prompt, "score": best_score, "version_id": new_version["id"]}
    return None

def _arg(name: str, default: int) -> int:
    if name in sys.argv:
        idx = sys.argv.index(name) + 1
        if idx < len(sys.argv):
            try:
                return max(1, int(sys.argv[idx]))
            except Exception:
                return default
    return default


def main() -> None:
    min_samples = _arg("--min-samples", 3)
    min_principle_count = _arg("--min-principle-count", 3)

    from lib.memory import Memory

    summary = {
        "min_samples": min_samples,
        "min_principle_count": min_principle_count,
        "domains": [],
    }
    with Memory() as mem:
        conn = mem._conn  # internal use in offline maintenance script
        rows = conn.execute(
            "SELECT domain, COUNT(*) AS c FROM run_episodes GROUP BY domain ORDER BY c DESC"
        ).fetchall()
        domains = [str(r["domain"] or "general") for r in rows if int(r["c"] or 0) > 0]
        for domain in domains:
            empirical_id = mem.upsert_empirical_strategy(domain=domain, min_samples=min_samples)
            inserted_principles = mem.synthesize_principles_from_episodes(
                domain=domain, min_count=min_principle_count
            )
            
            # Phase 4: Auto-Prompt Optimization
            prompt_opt = run_auto_prompt_optimization(domain, mem)
            
            summary["domains"].append(
                {
                    "domain": domain,
                    "empirical_strategy_id": empirical_id,
                    "inserted_principle_ids": inserted_principles,
                    "inserted_principles_count": len(inserted_principles),
                    "auto_prompt_optimization": prompt_opt
                }
            )
        mem.record_memory_decision(
            decision_type="memory_consolidation_run",
            details=summary,
            phase="consolidation",
            confidence=0.85,
        )

    out_path = ROOT / "memory" / "consolidation_last.json"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(summary, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps({"ok": True, "domains": len(summary["domains"]), "output": str(out_path)}))


if __name__ == "__main__":
    main()
