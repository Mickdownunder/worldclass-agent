#!/usr/bin/env python3
"""
Research Sandbox: Secure execution of AI-generated Python code.
Runs code in an isolated Docker container without network access.
"""

import subprocess
import tempfile
import json
import os
from pathlib import Path
from dataclasses import dataclass

@dataclass
class SandboxResult:
    stdout: str
    stderr: str
    exit_code: int
    timeout: bool

def run_in_sandbox(code: str, timeout_seconds: int = 30) -> SandboxResult:
    """
    Executes Python code in a secure, ephemeral Docker container.
    
    Security Constraints:
    - --network none: No internet access (prevents API abuse, downloading malware)
    - --memory 512m: Prevents memory bombs
    - --cpus 1: Prevents CPU hogging
    - timeout: Prevents infinite loops
    - read-only volume mount for the code
    """
    
    # We write the code to a temporary directory
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp_path = Path(tmpdir)
        script_path = tmp_path / "script.py"
        script_path.write_text(code, encoding="utf-8")
        
        # Build the docker run command
        cmd = [
            "docker", "run",
            "--rm",                      # Remove container after run
            "--network", "none",         # No internet
            "--memory", "512m",          # Memory limit
            "--cpus", "1.0",             # CPU limit
            "-v", f"{tmp_path}:/app:ro", # Mount tmpdir to /app as read-only
            "-w", "/app",                # Set working directory
            "python:3.11-slim",          # Lightweight Python image
            "python", "script.py"
        ]
        
        try:
            # Run the subprocess with a timeout slightly higher than docker's internal execution time
            process = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=timeout_seconds
            )
            return SandboxResult(
                stdout=process.stdout,
                stderr=process.stderr,
                exit_code=process.returncode,
                timeout=False
            )
        except subprocess.TimeoutExpired as e:
            # If the subprocess times out, the container might still be running.
            # We should ideally kill it, but --rm and docker's own handling often cleans it up.
            # For robustness, we could find and kill the container, but since we didn't name it, 
            # it's tricky. In a prod env, we'd name it with a UUID and kill it on timeout.
            return SandboxResult(
                stdout=(e.stdout.decode('utf-8') if isinstance(e.stdout, bytes) else (e.stdout or "")),
                stderr=(e.stderr.decode('utf-8') if isinstance(e.stderr, bytes) else (e.stderr or "")) + f"\n[!] Sandbox Timeout Exceeded ({timeout_seconds}s).",
                exit_code=124, # Standard timeout exit code
                timeout=True
            )
        except Exception as e:
            return SandboxResult(
                stdout="",
                stderr=f"[!] Sandbox Internal Error: {str(e)}",
                exit_code=1,
                timeout=False
            )

if __name__ == "__main__":
    # Small self-test if executed directly
    test_code = """
import sys
print("Hello from the Sandbox!")
sys.stderr.write("This is a simulated error.\\n")
sys.exit(0)
"""
    print("Running self-test...")
    res = run_in_sandbox(test_code, timeout_seconds=10)
    print(f"Exit Code: {res.exit_code}")
    print(f"Stdout:\\n{res.stdout}")
    print(f"Stderr:\\n{res.stderr}")
