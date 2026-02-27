import { execFile, spawn } from "child_process";
import { promisify } from "util";
import path from "path";
import { appendFile, mkdir, readFile, writeFile } from "fs/promises";
import { tmpdir } from "os";
import { join } from "path";
import { OPERATOR_ROOT } from "./config";

const exec = promisify(execFile);
const OP_BIN = path.join(OPERATOR_ROOT, "bin", "op");
const BRAIN_BIN = path.join(OPERATOR_ROOT, "bin", "brain");
const AUDIT_LOG = path.join(OPERATOR_ROOT, "logs", "ui-audit.log");
const SEND_TELEGRAM = path.join(OPERATOR_ROOT, "tools", "send-telegram.sh");
const RUN_UNTIL_DONE = path.join(OPERATOR_ROOT, "tools", "run-research-cycle-until-done.sh");

/** Workflows allowed to be triggered from the UI */
export const ALLOWED_WORKFLOWS = new Set([
  "factory-cycle",
  "research-init",
  "research-cycle",
  "autopilot-infra",
  "planner",
  "signals",
  "infra-status",
  "knowledge-commit",
  "goal-progress",
  "opportunity-discovery",
  "opportunity-ingest",
  "opportunity-select",
  "opportunity-dispatch",
  "queue-run",
  "queue-notify",
  "critic",
  "prioritize",
]);

async function audit(action: string, params: Record<string, unknown>, result: { ok: boolean; message?: string }) {
  try {
    await mkdir(path.dirname(AUDIT_LOG), { recursive: true });
    const line = `${new Date().toISOString()} | ${action} | ${JSON.stringify(params)} | ${JSON.stringify(result)}\n`;
    await appendFile(AUDIT_LOG, line);
  } catch {
    //
  }
}

export async function runWorkflow(workflowId: string, request = ""): Promise<{ ok: boolean; jobId?: string; error?: string }> {
  if (!ALLOWED_WORKFLOWS.has(workflowId)) {
    await audit("run-workflow", { workflowId, request }, { ok: false, message: "workflow not allowed" });
    return { ok: false, error: "Workflow not allowed" };
  }
  try {
    const { stdout: jobDir } = await exec(OP_BIN, ["job", "new", "--workflow", workflowId, "--request", request || "ui-trigger"], {
      timeout: 5000,
      env: { ...process.env },
    });
    const jobId = jobDir.trim().split("/").pop() ?? jobDir.trim();
    const runArgs = workflowId === "research-cycle" ? ["run", jobId, "--timeout", "900"] : ["run", jobId];
    spawn(OP_BIN, runArgs, { env: process.env, stdio: "ignore", detached: true }).unref();
    await audit("run-workflow", { workflowId, request, jobId }, { ok: true });
    await notifyTelegram(`[UI] Started workflow: ${workflowId} → job ${jobId}`);
    return { ok: true, jobId };
  } catch (e) {
    const err = String((e as Error).message);
    await audit("run-workflow", { workflowId, request }, { ok: false, message: err });
    return { ok: false, error: err };
  }
}

export async function retryJob(jobId: string): Promise<{ ok: boolean; error?: string }> {
  try {
    spawn(OP_BIN, ["retry", jobId], { env: process.env, stdio: "ignore", detached: true }).unref();
    await audit("retry", { jobId }, { ok: true });
    await notifyTelegram(`[UI] Retry job: ${jobId}`);
    return { ok: true };
  } catch (e) {
    const err = String((e as Error).message);
    await audit("retry", { jobId }, { ok: false, message: err });
    return { ok: false, error: err };
  }
}

export async function runFactoryCycle(): Promise<{ ok: boolean; jobId?: string; error?: string }> {
  return runWorkflow("factory-cycle", "ui-trigger");
}

/**
 * Run research-init (wait for completion), read project_id, then spawn run-research-cycle-until-done.sh
 * so all phases run automatically without clicking "Nächste Phase".
 */
export async function runResearchInitAndCycleUntilDone(
  question: string,
  researchMode: "standard" | "frontier" = "standard"
): Promise<{ ok: boolean; jobId?: string; projectId?: string; error?: string }> {
  try {
    const requestPayload = JSON.stringify({ question: question || "ui-trigger", research_mode: researchMode });
    const { stdout: jobDirRaw } = await exec(OP_BIN, ["job", "new", "--workflow", "research-init", "--request", requestPayload], {
      timeout: 5000,
      env: { ...process.env },
    });
    const jobDir = jobDirRaw.trim();
    const jobId = jobDir.split("/").pop() ?? jobDir;
    await exec(OP_BIN, ["run", jobDir, "--timeout", "120"], {
      timeout: 130_000,
      env: { ...process.env },
    });
    const projectIdPath = path.join(jobDir, "artifacts", "project_id.txt");
    let projectId: string | undefined;
    try {
      const raw = await readFile(projectIdPath, "utf-8");
      projectId = raw.trim();
    } catch {
      await audit("research-init-and-cycle", { question, jobId }, { ok: false, message: "no project_id in artifacts" });
      return { ok: false, jobId, error: "Init-Job lief, aber project_id nicht gefunden." };
    }
    if (!projectId) {
      return { ok: false, jobId, error: "project_id leer." };
    }
    spawn("bash", [RUN_UNTIL_DONE, projectId], {
      cwd: OPERATOR_ROOT,
      env: process.env,
      stdio: "ignore",
      detached: true,
    }).unref();
    await audit("research-init-and-cycle", { question, jobId, projectId }, { ok: true });
    await notifyTelegram(`[UI] Research gestartet: ${projectId} – alle Phasen laufen automatisch.`);
    return { ok: true, jobId, projectId };
  } catch (e) {
    const err = String((e as Error).message);
    await audit("research-init-and-cycle", { question }, { ok: false, message: err });
    return { ok: false, error: err };
  }
}

async function notifyTelegram(message: string): Promise<void> {
  if (process.env.UI_TELEGRAM_NOTIFY !== "1") return;
  try {
    const tmp = join(tmpdir(), `operator-ui-${Date.now()}.txt`);
    await writeFile(tmp, message, "utf-8");
    spawn("bash", [SEND_TELEGRAM, tmp], { env: process.env, stdio: "ignore", detached: true }).unref();
  } catch {
    //
  }
}

export async function runBrainCycle(goal = "Decide and execute the most impactful next action"): Promise<{ ok: boolean; error?: string }> {
  try {
    spawn(BRAIN_BIN, ["cycle", "--goal", goal], { env: process.env, stdio: "ignore", detached: true }).unref();
    await audit("brain-cycle", { goal }, { ok: true });
    await notifyTelegram(`[UI] Brain cycle started: ${goal.slice(0, 60)}…`);
    return { ok: true };
  } catch (e) {
    const err = String((e as Error).message);
    await audit("brain-cycle", { goal }, { ok: false, message: err });
    return { ok: false, error: err };
  }
}
