import { execFileSync, execSync } from "node:child_process";
import { writeFileSync, mkdtempSync, readFileSync, existsSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";

const OP = "/root/operator/bin/op";
const DISPATCH = "/root/operator/tools/operator-dispatch/bin/operator-dispatch";
const JOBS_BASE = "/root/operator/jobs";

function runOp(args: string[], timeoutMs = 60_000): string {
  try {
    return execFileSync(OP, args, {
      encoding: "utf8",
      timeout: timeoutMs,
    }).trim();
  } catch (e: any) {
    const msg = e.stderr?.trim() || e.message || "unknown error";
    throw new Error(`op ${args.join(" ")} failed: ${msg}`);
  }
}

function runDispatch(args: string[], timeoutMs = 60_000): string {
  try {
    return execFileSync(DISPATCH, args, {
      encoding: "utf8",
      timeout: timeoutMs,
    }).trim();
  } catch (e: any) {
    const msg = e.stderr?.trim() || e.message || "unknown error";
    throw new Error(`dispatch ${args.join(" ")} failed: ${msg}`);
  }
}

function runShell(cmd: string, timeoutMs = 120_000): string {
  try {
    return execSync(cmd, {
      encoding: "utf8",
      shell: "/bin/bash",
      timeout: timeoutMs,
    }).trim();
  } catch (e: any) {
    const msg = e.stderr?.trim() || e.message || "unknown error";
    throw new Error(`shell failed: ${msg}`);
  }
}

function makeRequest(workflow: string, text: string): string {
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

function latestFile(pattern: string): string | null {
  try {
    const cmd = `find ${JOBS_BASE} -name '${pattern}' -printf '%T@ %p\\n' 2>/dev/null | sort -n | tail -n 1 | cut -d' ' -f2-`;
    const p = runShell(cmd, 10_000);
    return p || null;
  } catch {
    return null;
  }
}

function readFileSafe(path: string): string {
  try {
    return readFileSync(path, "utf8").trim();
  } catch {
    return "";
  }
}

function truncate(text: string, maxLen = 4000): string {
  if (text.length <= maxLen) return text;
  return text.slice(0, maxLen) + "\n... (truncated)";
}

export default function (api: any) {
  api.registerCommand({
    name: "do",
    description: "Create an operator job (plan-only). Usage: /do <text>",
    acceptsArgs: true,
    requireAuth: true,
    handler: async (ctx: any) => {
      const text = (ctx.args || "").trim();
      if (!text) return { text: "Usage: /do <text>" };

      try {
        const reqPath = makeRequest("planner", text);
        const jobId = runDispatch(["create", "--request", reqPath]);

        return {
          text:
            `Job created: ${jobId}\n\n` +
            `Commands:\n` +
            `  /run ${jobId}\n` +
            `  /job-status ${jobId}\n` +
            `  /job-artifacts ${jobId}`,
        };
      } catch (e: any) {
        return { text: `Failed to create job: ${e.message}` };
      }
    },
  });

  api.registerCommand({
    name: "run",
    description: "Run an operator job. Usage: /run <job_id>",
    acceptsArgs: true,
    requireAuth: true,
    handler: async (ctx: any) => {
      const jobId = (ctx.args || "").trim();
      if (!jobId) return { text: "Usage: /run <job_id>" };

      try {
        const status = runDispatch(["run", jobId], 300_000);
        return { text: `Job ${jobId}: ${status}` };
      } catch (e: any) {
        return { text: `Run failed: ${e.message}` };
      }
    },
  });

  api.registerCommand({
    name: "job-status",
    description: "Get job status. Usage: /job-status [job_id]",
    acceptsArgs: true,
    requireAuth: true,
    handler: async (ctx: any) => {
      const jobId = (ctx.args || "").trim();

      try {
        if (!jobId) {
          const list = runOp(["job", "status", "--limit", "10"]);
          return { text: list ? `Recent jobs:\n\n${list}` : "No jobs found." };
        }

        const status = runDispatch(["status", jobId]);
        return { text: `${jobId}: ${status}` };
      } catch (e: any) {
        return { text: `Status check failed: ${e.message}` };
      }
    },
  });

  api.registerCommand({
    name: "job-artifacts",
    description: "List job artifacts. Usage: /job-artifacts <job_id>",
    acceptsArgs: true,
    requireAuth: true,
    handler: async (ctx: any) => {
      const jobId = (ctx.args || "").trim();
      if (!jobId) return { text: "Usage: /job-artifacts <job_id>" };

      try {
        const files = runDispatch(["artifacts", jobId]);
        return { text: files ? `Artifacts:\n${files}` : "No artifacts." };
      } catch (e: any) {
        return { text: `Failed: ${e.message}` };
      }
    },
  });

  api.registerCommand({
    name: "health",
    description: "System health check. Usage: /health",
    acceptsArgs: false,
    requireAuth: true,
    handler: async () => {
      try {
        const result = runOp(["healthcheck"]);
        const h = JSON.parse(result);
        const status = h.healthy ? "HEALTHY" : "DEGRADED";
        let msg = `System: ${status}\n`;
        msg += `Disk: ${h.disk_used_pct}%\n`;
        msg += `Load: ${h.load_1m ?? "n/a"}\n`;
        msg += `Jobs: ${h.jobs_total} total, ${h.jobs_failed} failed, ${h.jobs_running} running\n`;
        msg += `Policy: ${h.policy}`;
        if (h.recent_failures?.length) {
          msg += `\n\nRecent failures:\n${h.recent_failures.map((f: string) => `  - ${f}`).join("\n")}`;
        }
        return { text: msg };
      } catch (e: any) {
        return { text: `Health check failed: ${e.message}` };
      }
    },
  });

  api.registerCommand({
    name: "oqueue",
    description: "Show latest factory queue. Usage: /oqueue",
    acceptsArgs: false,
    requireAuth: true,
    handler: async () => {
      try {
        runShell(
          `${OP} job new --workflow queue-notify --request telegram | xargs -I{} ${OP} run {}`,
          30_000
        );

        const p = latestFile("telegram.txt");
        if (!p) return { text: "No queue found." };

        const msg = readFileSafe(p);
        return { text: msg || "Queue empty." };
      } catch (e: any) {
        return { text: `Queue check failed: ${e.message}` };
      }
    },
  });

  api.registerCommand({
    name: "qrun",
    description: "Run one item from latest queue. Usage: /qrun <index>",
    acceptsArgs: true,
    requireAuth: true,
    handler: async (ctx: any) => {
      const idx = (ctx.args || "").trim();
      if (!idx || isNaN(Number(idx))) return { text: "Usage: /qrun <index> (number)" };

      try {
        runShell(
          `RUN_MODE=index RUN_INDEX=${idx} ${OP} job new --workflow queue-run --request telegram | xargs -I{} ${OP} run {}`,
          300_000
        );

        const p = latestFile("ran.md");
        if (!p) return { text: `Started queue item ${idx}. (no result file yet)` };

        return { text: truncate(readFileSafe(p)) };
      } catch (e: any) {
        return { text: `Queue run failed: ${e.message}` };
      }
    },
  });

  api.registerCommand({
    name: "qrunall",
    description: "Run all items from latest queue. Usage: /qrunall",
    acceptsArgs: false,
    requireAuth: true,
    handler: async () => {
      try {
        runShell(
          `RUN_MODE=all ${OP} job new --workflow queue-run --request telegram | xargs -I{} ${OP} run {}`,
          600_000
        );

        const p = latestFile("ran.md");
        if (!p) return { text: "Queue run started. (no result file yet)" };

        return { text: truncate(readFileSafe(p)) };
      } catch (e: any) {
        return { text: `Queue run failed: ${e.message}` };
      }
    },
  });

  api.registerCommand({
    name: "factory",
    description: "Run full factory cycle (discover + match + pack + deliver). Usage: /factory",
    acceptsArgs: false,
    requireAuth: true,
    handler: async () => {
      try {
        const jobDir = runOp(["job", "new", "--workflow", "factory-cycle", "--request", "telegram trigger"]);
        runOp(["run", jobDir], 300_000);

        const p = latestFile("telegram.txt");
        const msg = p ? readFileSafe(p) : "";

        return {
          text: msg
            ? `Factory cycle complete.\n\n${truncate(msg)}`
            : "Factory cycle complete. No delivery generated.",
        };
      } catch (e: any) {
        return { text: `Factory cycle failed: ${e.message}` };
      }
    },
  });

  api.registerCommand({
    name: "think",
    description: "Ask the brain to think about a goal. Usage: /think <goal>",
    acceptsArgs: true,
    requireAuth: true,
    handler: async (ctx: any) => {
      const goal = (ctx.args || "").trim() || "Decide the most impactful next action";
      try {
        const result = runShell(
          `source /root/operator/conf/secrets.env 2>/dev/null; /root/operator/bin/brain think --goal '${goal.replace(/'/g, "'\\''")}'`,
          120_000
        );
        const plan = JSON.parse(result);
        let msg = `Brain Analysis:\n${plan.analysis || "none"}\n\nConfidence: ${plan.confidence || "?"}\n\nPlan:`;
        for (const a of (plan.plan || [])) {
          msg += `\n- [${a.urgency || "?"}] ${a.action}: ${a.reason || ""}`;
        }
        if (plan.risks?.length) {
          msg += `\n\nRisks:\n${plan.risks.map((r: string) => `- ${r}`).join("\n")}`;
        }
        return { text: truncate(msg) };
      } catch (e: any) {
        return { text: `Think failed: ${e.message}` };
      }
    },
  });

  api.registerCommand({
    name: "cycle",
    description: "Run a full cognitive cycle. Usage: /cycle [goal]",
    acceptsArgs: true,
    requireAuth: true,
    handler: async (ctx: any) => {
      const goal = (ctx.args || "").trim() || "Decide and execute the most impactful next action";
      try {
        const result = runShell(
          `source /root/operator/conf/secrets.env 2>/dev/null; /root/operator/bin/brain cycle --goal '${goal.replace(/'/g, "'\\''")}'`,
          300_000
        );
        const cycle = JSON.parse(result);
        let msg = `Cognitive Cycle Complete\n\n`;
        msg += `Decision: ${cycle.decision || "none"}\n`;
        msg += `Status: ${cycle.status || "?"}\n`;
        msg += `Quality: ${cycle.quality || "?"}\n`;
        msg += `Executed: ${cycle.executed ? "yes" : "no"}\n`;
        if (cycle.learnings) msg += `\nLearnings: ${cycle.learnings}`;
        if (cycle.should_retry) msg += `\n\nShould retry: yes`;
        return { text: truncate(msg) };
      } catch (e: any) {
        return { text: `Cycle failed: ${e.message}` };
      }
    },
  });

  api.registerCommand({
    name: "memory",
    description: "Query agent memory. Usage: /memory [search query]",
    acceptsArgs: true,
    requireAuth: true,
    handler: async (ctx: any) => {
      const query = (ctx.args || "").trim();
      try {
        const args = query ? `--query '${query.replace(/'/g, "'\\''")}'` : "";
        const result = runShell(`/root/operator/bin/brain memory ${args}`, 10_000);
        const data = JSON.parse(result);
        if (query) {
          const eps = (data.episodes || []).slice(0, 5);
          const refs = (data.reflections || []).slice(0, 3);
          let msg = `Memory search: "${query}"\n\nEpisodes (${eps.length}):`;
          for (const e of eps) msg += `\n- [${e.kind}] ${e.content?.slice(0, 100)}`;
          if (refs.length) {
            msg += `\n\nReflections (${refs.length}):`;
            for (const r of refs) msg += `\n- [q=${r.quality}] ${r.learnings?.slice(0, 100)}`;
          }
          return { text: truncate(msg) };
        } else {
          const t = data.totals || {};
          let msg = `Memory State\n\n`;
          msg += `Episodes: ${t.episodes || 0}\n`;
          msg += `Decisions: ${t.decisions || 0}\n`;
          msg += `Reflections: ${t.reflections || 0}\n`;
          msg += `Avg Quality: ${t.avg_quality || 0}\n`;
          if (data.playbooks?.length) {
            msg += `\nPlaybooks (${data.playbooks.length}):`;
            for (const p of data.playbooks) msg += `\n- ${p.domain}: ${p.strategy?.slice(0, 80)}`;
          }
          return { text: truncate(msg) };
        }
      } catch (e: any) {
        return { text: `Memory query failed: ${e.message}` };
      }
    },
  });

  api.registerCommand({
    name: "clients",
    description: "List configured clients. Usage: /clients",
    acceptsArgs: false,
    requireAuth: true,
    handler: async () => {
      try {
        const out = runShell(
          `for f in /root/operator/factory/clients/*.json; do jq -r '"- " + .id + " (" + .name + ") topics=" + (.topics|join(","))' "$f" 2>/dev/null; done`,
          10_000
        );
        return { text: out ? `Configured clients:\n\n${out}` : "No clients configured." };
      } catch (e: any) {
        return { text: `Failed: ${e.message}` };
      }
    },
  });

  api.registerCommand({
    name: "skip",
    description: "Acknowledge queue without running. Usage: /skip",
    acceptsArgs: false,
    requireAuth: true,
    handler: async () => {
      return { text: "Queue acknowledged, skipped." };
    },
  });
}
