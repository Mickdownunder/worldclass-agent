#!/usr/bin/env python3
"""
Prompt Manager CLI
Allows viewing and rolling back auto-optimized system prompts.
"""

import sys
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
VERSIONS_FILE = ROOT / "memory" / "prompt_versions.json"

def load_versions():
    if not VERSIONS_FILE.exists():
        return []
    try:
        return json.loads(VERSIONS_FILE.read_text())
    except Exception:
        return []

def save_versions(versions):
    VERSIONS_FILE.parent.mkdir(parents=True, exist_ok=True)
    VERSIONS_FILE.write_text(json.dumps(versions, indent=2))

def list_versions(domain=None):
    versions = load_versions()
    if domain:
        versions = [v for v in versions if v.get("domain") == domain]
        
    if not versions:
        print("No prompt versions found.")
        return
        
    # Sort by created_at descending
    versions.sort(key=lambda x: x.get("created_at", ""), reverse=True)
    
    print(f"{'ID':<38} | {'DOMAIN':<15} | {'SCORE':<5} | {'STATUS':<10} | {'CREATED AT'}")
    print("-" * 95)
    for v in versions:
        vid = v.get("id", "unknown")
        dom = v.get("domain", "general")
        score = v.get("avg_score", 0.0)
        status = v.get("status", "unknown")
        ts = v.get("created_at", "")
        print(f"{vid:<38} | {dom:<15} | {score:<5.2f} | {status:<10} | {ts}")

def rollback(version_id: str):
    versions = load_versions()
    target = next((v for v in versions if v.get("id") == version_id), None)
    
    if not target:
        print(f"Error: Version {version_id} not found.")
        sys.exit(1)
        
    domain = target.get("domain")
    
    # Archive all active versions for this domain
    for v in versions:
        if v.get("domain") == domain and v.get("status") == "active":
            v["status"] = "archived"
            
    # Set target to active
    target["status"] = "active"
    
    save_versions(versions)
    print(f"Successfully rolled back domain '{domain}' to prompt version {version_id}.")
    print(f"Active prompt for {domain} is now:\n{target.get('prompt_text')}")

def get_active(domain: str):
    versions = load_versions()
    active = [v for v in versions if v.get("domain") == domain and v.get("status") == "active"]
    if not active:
        print(f"No active optimized prompt found for domain '{domain}'.")
    else:
        print(active[0].get("prompt_text"))

def main():
    if len(sys.argv) < 2:
        print("Usage:")
        print("  prompt_manager.py list [domain]")
        print("  prompt_manager.py rollback <version_id>")
        print("  prompt_manager.py active <domain>")
        sys.exit(1)
        
    cmd = sys.argv[1]
    
    if cmd == "list":
        domain = sys.argv[2] if len(sys.argv) > 2 else None
        list_versions(domain)
    elif cmd == "rollback":
        if len(sys.argv) < 3:
            print("Error: Missing version_id")
            sys.exit(1)
        rollback(sys.argv[2])
    elif cmd == "active":
        if len(sys.argv) < 3:
            print("Error: Missing domain")
            sys.exit(1)
        get_active(sys.argv[2])
    else:
        print(f"Unknown command: {cmd}")
        sys.exit(1)

if __name__ == "__main__":
    main()
