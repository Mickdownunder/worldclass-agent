import { execFileSync, execSync } from "node:child_process";
import { writeFileSync, mkdtempSync, readFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";

export const OP = "/root/operator/bin/op";
export const DISPATCH = "/root/operator/tools/operator-dispatch/bin/operator-dispatch";
export const JOBS_BASE = "/root/operator/jobs";
export const OPERATOR_ROOT = "/root/operator";

export function runOp(args: string[], timeoutMs = 60_000): string {
  try {
    return execFileSync(OP, args, {
      encoding: "utf8",
      timeout: timeoutMs,
    }).trim();
  } catch (e: unknown) {
    const err = e as { stderr?: string; message?: string };
    const msg = err.stderr?.trim() || err.message || "unknown error";
    throw new Error(`op ${args.join(" ")} failed: ${msg}`);
  }
}

export function runDispatch(args: string[], timeoutMs = 60_000): string {
  try {
    return execFileSync(DISPATCH, args, {
      encoding: "utf8",
      timeout: timeoutMs,
    }).trim();
  } catch (e: unknown) {
    const err = e as { stderr?: string; message?: string };
    const msg = err.stderr?.trim() || err.message || "unknown error";
    throw new Error(`dispatch ${args.join(" ")} failed: ${msg}`);
  }
}

export function runShell(cmd: string, timeoutMs = 120_000): string {
  try {
    return execSync(cmd, {
      encoding: "utf8",
      shell: "/bin/bash",
      timeout: timeoutMs,
    }).trim();
  } catch (e: unknown) {
    const err = e as { stderr?: string; message?: string };
    const msg = err.stderr?.trim() || err.message || "unknown error";
    throw new Error(`shell failed: ${msg}`);
  }
}

export function makeRequest(workflow: string, text: string): string {
  const req = {
    version: "1.0",
    source: { channel: "telegram", user_id: "openclaw" },
    intent: { type: "plan", workflow },
    payload: { text },
    governance: { policy: "READ_ONLY", write_scope: [] as string[] },
    routing: { reply: "summary" },
  };
  const dir = mkdtempSync(join(tmpdir(), "operator-req-"));
  const path = join(dir, "request.json");
  writeFileSync(path, JSON.stringify(req, null, 2));
  return path;
}

export function latestFile(pattern: string): string | null {
  try {
    const cmd = `find ${JOBS_BASE} -name '${pattern}' -printf '%T@ %p\\n' 2>/dev/null | sort -n | tail -n 1 | cut -d' ' -f2-`;
    const p = runShell(cmd, 10_000);
    return p || null;
  } catch {
    return null;
  }
}

export function readFileSafe(path: string): string {
  try {
    return readFileSync(path, "utf8").trim();
  } catch {
    return "";
  }
}

export function truncate(text: string, maxLen = 4000): string {
  if (text.length <= maxLen) return text;
  return text.slice(0, maxLen) + "\n... (truncated)";
}
