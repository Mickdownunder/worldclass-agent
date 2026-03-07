import { execFile, spawn } from "child_process";
import { promisify } from "util";
import path from "path";
import { appendFile, mkdir, writeFile } from "fs/promises";
import { tmpdir } from "os";
import { join } from "path";
import { OPERATOR_ROOT } from "./config";

const exec = promisify(execFile);
const OP_BIN = path.join(OPERATOR_ROOT, "bin", "op");
const BRAIN_BIN = path.join(OPERATOR_ROOT, "bin", "brain");
const AUDIT_LOG = path.join(OPERATOR_ROOT, "logs", "ui-audit.log");
const SEND_TELEGRAM = path.join(OPERATOR_ROOT, "tools", "send-telegram.sh");
const CONTROL_PLANE_INTAKE = path.join(OPERATOR_ROOT, "tools", "control_plane_intake.py");

export type ResearchMode = "standard" | "frontier" | "discovery";

export interface WorkflowResult {
  ok: boolean;
  jobId?: string;
  projectId?: string;
  requestEventId?: string;
  error?: string;
}

const VALID_RESEARCH_MODES = new Set<ResearchMode>(["standard", "frontier", "discovery"]);

/** Workflows allowed to be triggered from the UI (no factory/queue/opportunity) */
export const ALLOWED_WORKFLOWS = new Set([
  "research-init",
  "research-cycle",
  "autopilot-infra",
  "planner",
  "signals",
  "infra-status",
  "knowledge-commit",
  "goal-progress",
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

async function runControlPlaneIntake(args: string[], timeout = 150_000): Promise<Record<string, unknown>> {
  try {
    const result = await exec("python3", [CONTROL_PLANE_INTAKE, ...args], {
      timeout,
      env: { ...process.env, OPERATOR_ROOT },
    });
    const stdout = typeof result === "string" ? result : result.stdout;
    return JSON.parse((stdout || "{}").trim() || "{}");
  } catch (e) {
    const stdout = typeof (e as { stdout?: string }).stdout === "string" ? (e as { stdout?: string }).stdout?.trim() : "";
    if (stdout) {
      try {
        return JSON.parse(stdout);
      } catch {
        // fall through
      }
    }
    throw e;
  }
}

function normalizeWorkflowResult(payload: Record<string, unknown>): WorkflowResult {
  return {
    ok: payload.ok === true,
    jobId: typeof payload.jobId === "string" ? payload.jobId : undefined,
    projectId: typeof payload.projectId === "string" ? payload.projectId : undefined,
    requestEventId: typeof payload.requestEventId === "string" ? payload.requestEventId : undefined,
    error: typeof payload.error === "string" ? payload.error : undefined,
  };
}

async function submitResearchContinueIntent(projectId: string): Promise<WorkflowResult> {
  if (!/^proj-[a-zA-Z0-9_-]+$/.test(projectId)) {
    return { ok: false, error: "Ungültige projectId" };
  }
  try {
    const payload = await runControlPlaneIntake(["ui-research-continue", "--project-id", projectId]);
    const result = normalizeWorkflowResult(payload);
    await audit(
      "control-plane-research-continue",
      { projectId, requestEventId: result.requestEventId },
      { ok: result.ok, message: result.error }
    );
    if (result.ok) {
      await notifyTelegram(`[UI] Research cycle submitted to control plane: ${projectId}`);
    }
    return result;
  } catch (e) {
    const err = String((e as Error).message);
    await audit("control-plane-research-continue", { projectId }, { ok: false, message: err });
    return { ok: false, error: err };
  }
}

export async function submitResearchStartIntent(
  question: string,
  researchMode: ResearchMode = "standard",
  runUntilDone = true
): Promise<WorkflowResult> {
  const cleanQuestion = question.trim();
  if (!cleanQuestion) {
    return { ok: false, error: "question ist erforderlich" };
  }
  const mode = VALID_RESEARCH_MODES.has(researchMode) ? researchMode : "standard";
  try {
    const payload = await runControlPlaneIntake(
      [
        "ui-research-start",
        "--question",
        cleanQuestion,
        "--research-mode",
        mode,
        "--run-until-done",
        runUntilDone ? "1" : "0",
      ],
      150_000
    );
    const result = normalizeWorkflowResult(payload);
    await audit(
      "control-plane-research-start",
      {
        question: cleanQuestion.slice(0, 160),
        researchMode: mode,
        runUntilDone,
        projectId: result.projectId,
        requestEventId: result.requestEventId,
      },
      { ok: result.ok, message: result.error }
    );
    if (result.ok) {
      const suffix = runUntilDone ? " – alle Phasen laufen automatisch." : ".";
      await notifyTelegram(`[UI] Research gestartet: ${result.projectId ?? "pending"}${suffix}`);
    }
    return result;
  } catch (e) {
    const err = String((e as Error).message);
    await audit(
      "control-plane-research-start",
      { question: cleanQuestion.slice(0, 160), researchMode: mode, runUntilDone },
      { ok: false, message: err }
    );
    return { ok: false, error: err };
  }
}

export async function runWorkflow(workflowId: string, request = ""): Promise<WorkflowResult> {
  if (!ALLOWED_WORKFLOWS.has(workflowId)) {
    await audit("run-workflow", { workflowId, request }, { ok: false, message: "workflow not allowed" });
    return { ok: false, error: "Workflow not allowed" };
  }
  try {
    if (workflowId === "research-cycle") {
      return await submitResearchContinueIntent(request.trim());
    }
    const { stdout: jobDir } = await exec(OP_BIN, ["job", "new", "--workflow", workflowId, "--request", request || "ui-trigger"], {
      timeout: 5000,
      env: { ...process.env },
    });
    const jobId = jobDir.trim().split("/").pop() ?? jobDir.trim();
    const runArgs = ["run", jobId];
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

export async function runResearchInitAndCycleUntilDone(
  question: string,
  researchMode: ResearchMode = "standard"
): Promise<WorkflowResult> {
  return submitResearchStartIntent(question, researchMode, true);
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
