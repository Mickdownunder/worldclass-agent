import { NextRequest, NextResponse } from "next/server";
import { getSession } from "@/lib/auth/session";
import { readFile, access } from "fs/promises";
import path from "path";
import { OPERATOR_ROOT } from "@/lib/operator/config";

export const dynamic = "force-dynamic";

const RESEARCH_ROOT = path.join(OPERATOR_ROOT, "research");
const HEARTBEAT_FRESH_MS = 30_000;
const STUCK_NO_PROGRESS_MS = 300_000;
const ERROR_LOOP_WINDOW_MS = 5 * 60 * 1000;
const ERROR_LOOP_COUNT = 3;
const MAX_EVENTS = 200;

export type RuntimeState =
  | "RUNNING"
  | "IDLE"
  | "STUCK"
  | "ERROR_LOOP"
  | "FAILED"
  | "DONE";

function safeProjectPath(projectId: string): string {
  const PROJECT_ID_RE = /^proj-[a-zA-Z0-9_-]+$/;
  if (!PROJECT_ID_RE.test(projectId)) {
    throw new Error("Invalid project ID");
  }
  const resolved = path.resolve(RESEARCH_ROOT, projectId);
  if (!resolved.startsWith(RESEARCH_ROOT + path.sep)) {
    throw new Error("Invalid project path");
  }
  return resolved;
}

async function pidAlive(pid: number): Promise<boolean> {
  if (typeof pid !== "number" || pid <= 0) return false;
  try {
    await access(`/proc/${pid}`, 0);
    return true;
  } catch {
    return false;
  }
}

interface ProgressData {
  pid?: number;
  alive?: boolean;
  heartbeat?: string;
  phase?: string;
  step?: string;
  step_started_at?: string;
  step_index?: number;
  step_total?: number;
  steps_completed?: Array<{ ts: string; step: string; duration_s: number }>;
  started_at?: string;
  last_error?: { code: string; message: string; at: string };
}

interface LogEvent {
  ts: string;
  event: string;
  code?: string;
  message?: string;
  step?: string;
  phase?: string;
  [k: string]: unknown;
}

function parseEventsJsonl(content: string): LogEvent[] {
  const lines = content.trim().split("\n").filter(Boolean);
  const out: LogEvent[] = [];
  for (const line of lines) {
    try {
      out.push(JSON.parse(line) as LogEvent);
    } catch {
      // skip malformed lines
    }
  }
  return out;
}

function computeState(
  projectStatus: string,
  progress: ProgressData | null,
  nowMs: number,
  errorCounts5m: Record<string, number>,
  _events: LogEvent[]
): {
  state: RuntimeState;
  stuck_reason: string | null;
  loop_signature: string | null;
} {
  if (projectStatus === "done") {
    return { state: "DONE", stuck_reason: null, loop_signature: null };
  }
  if (
    projectStatus === "cancelled" ||
    projectStatus.startsWith("failed_") ||
    projectStatus === "failed"
  ) {
    return { state: "FAILED", stuck_reason: null, loop_signature: null };
  }

  if (!progress || !progress.heartbeat) {
    return { state: "IDLE", stuck_reason: null, loop_signature: null };
  }

  const heartbeatMs = new Date(progress.heartbeat).getTime();
  const heartbeatAgeMs = nowMs - heartbeatMs;
  const stepStartedAt = progress.step_started_at || progress.heartbeat;
  const stepStartedMs = new Date(stepStartedAt).getTime();
  const stepAgeMs = nowMs - stepStartedMs;

  // Error loop: same error code >= ERROR_LOOP_COUNT in last 5 min
  const loopEntry = Object.entries(errorCounts5m).find(
    ([, n]) => n >= ERROR_LOOP_COUNT
  );
  const loop_signature = loopEntry ? loopEntry[0] : null;
  if (loop_signature) {
    return {
      state: "ERROR_LOOP",
      stuck_reason: null,
      loop_signature,
    };
  }

  if (heartbeatAgeMs >= HEARTBEAT_FRESH_MS) {
    return { state: "IDLE", stuck_reason: null, loop_signature: null };
  }

  // Heartbeat fresh -> RUNNING or STUCK
  if (stepAgeMs >= STUCK_NO_PROGRESS_MS) {
    return {
      state: "STUCK",
      stuck_reason: `no_step_change_${Math.round(stepAgeMs / 1000)}s`,
      loop_signature: null,
    };
  }

  return { state: "RUNNING", stuck_reason: null, loop_signature: null };
}

export async function GET(
  _request: NextRequest,
  { params }: { params: Promise<{ id: string }> }
) {
  const ok = await getSession();
  if (!ok) return NextResponse.json({ error: "Unauthorized" }, { status: 401 });
  const id = (await params).id;
  if (!id) return NextResponse.json({ error: "Missing id" }, { status: 400 });

  try {
    const projPath = safeProjectPath(id);
    const nowMs = Date.now();
    const fiveMinAgo = nowMs - ERROR_LOOP_WINDOW_MS;

    let projectStatus = "active";
    try {
      const projectRaw = await readFile(
        path.join(projPath, "project.json"),
        "utf8"
      );
      const project = JSON.parse(projectRaw) as { status?: string };
      projectStatus = project.status ?? "active";
    } catch {
      // keep default
    }

    let progressData: ProgressData | null = null;
    const progressPath = path.join(projPath, "progress.json");
    try {
      const raw = await readFile(progressPath, "utf8");
      progressData = JSON.parse(raw) as ProgressData;
    } catch {
      const noProgressState =
        projectStatus === "done"
          ? "DONE"
          : projectStatus === "cancelled" || projectStatus.startsWith("failed_") || projectStatus === "failed"
            ? "FAILED"
            : "IDLE";
      return NextResponse.json({
        state: noProgressState,
        is_running: false,
        data: null,
        heartbeat_at: null,
        heartbeat_age_s: null,
        pid_alive: false,
        last_progress_at: null,
        last_error: null,
        error_counts_5m: {},
        loop_signature: null,
        stuck_reason: null,
        phase: null,
        step: null,
        step_started_at: null,
        events: [],
        project_status: projectStatus,
      });
    }

    const heartbeatAt = progressData.heartbeat || null;
    const heartbeatMs = heartbeatAt ? new Date(heartbeatAt).getTime() : 0;
    const heartbeatAgeS =
      heartbeatMs > 0 ? (nowMs - heartbeatMs) / 1000 : null;
    const pid = progressData.pid;
    const pid_alive =
      typeof pid === "number" ? await pidAlive(pid) : false;
    const lastProgressAt = progressData.heartbeat || progressData.started_at || null;
    const lastError = progressData.last_error ?? null;

    let events: LogEvent[] = [];
    try {
      const eventsPath = path.join(projPath, "events.jsonl");
      const eventsContent = await readFile(eventsPath, "utf8");
      events = parseEventsJsonl(eventsContent);
    } catch {
      // no events file yet
    }

    const errorCounts5m: Record<string, number> = {};
    for (const e of events) {
      if (e.event !== "error" || !e.code) continue;
      const ts = new Date(e.ts).getTime();
      if (ts < fiveMinAgo) continue;
      errorCounts5m[e.code] = (errorCounts5m[e.code] ?? 0) + 1;
    }

    const { state, stuck_reason, loop_signature } = computeState(
      projectStatus,
      progressData,
      nowMs,
      errorCounts5m,
      events
    );

    const is_running = state === "RUNNING";
    const eventsSlice = events.slice(-MAX_EVENTS);

    return NextResponse.json({
      state,
      is_running,
      data: progressData,
      heartbeat_at: heartbeatAt,
      heartbeat_age_s: heartbeatAgeS,
      pid_alive: pid_alive,
      last_progress_at: lastProgressAt,
      last_error: lastError,
      error_counts_5m: errorCounts5m,
      loop_signature,
      stuck_reason,
      phase: progressData.phase ?? null,
      step: progressData.step ?? null,
      step_started_at: progressData.step_started_at ?? null,
      events: eventsSlice,
      project_status: projectStatus,
    });
  } catch (e) {
    return NextResponse.json(
      { error: String((e as Error).message) },
      { status: 500 }
    );
  }
}
