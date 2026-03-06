import { NextRequest, NextResponse } from "next/server";
import { readFile } from "fs/promises";
import path from "path";
import { OPERATOR_ROOT } from "@/lib/operator/config";
import { listJobs } from "@/lib/operator/jobs";
import { getHealth } from "@/lib/operator/health";
import { listResearchProjects } from "@/lib/operator/research";
import { getSession } from "@/lib/auth/session";

export const dynamic = "force-dynamic";
export const runtime = "nodejs";

const LOG_FILE = path.join(OPERATOR_ROOT, "logs", "agent-activity.jsonl");
const MAX_ACTIVITY = 100;
const STREAM_INTERVAL_MS = 4000;
const PING_INTERVAL_MS = 15000;

interface AgentActivityEntry {
  ts: string;
  from: string;
  to: string;
  plan: string;
  request?: string;
  command?: string;
  overall?: string;
  recommendation?: string;
  atlas_overall?: string;
  atlas_recommendation?: string;
  run_dir?: string;
}

function parseJsonl(raw: string): AgentActivityEntry[] {
  const entries: AgentActivityEntry[] = [];
  const lines = raw.split("\n");
  let buffer = "";
  let depth = 0;

  for (const line of lines) {
    buffer += (buffer ? "\n" : "") + line;
    for (const c of line) {
      if (c === "{") depth += 1;
      else if (c === "}") depth -= 1;
    }
    if (depth === 0 && buffer.trim()) {
      try {
        const e = JSON.parse(buffer) as AgentActivityEntry;
        if (e.ts && e.from && e.to) entries.push(e);
      } catch {
        // ignore malformed
      }
      buffer = "";
    }
  }

  if (buffer.trim()) {
    try {
      const e = JSON.parse(buffer) as AgentActivityEntry;
      if (e.ts && e.from && e.to) entries.push(e);
    } catch {
      // ignore malformed tail
    }
  }

  return entries;
}

let cachedProjects: Awaited<ReturnType<typeof listResearchProjects>> = [];
let cachedProjectsAt = 0;
const PROJECTS_TTL_MS = 20000;

async function buildSnapshot() {
  const raw = await readFile(LOG_FILE, "utf-8").catch(() => "");
  const all = parseJsonl(raw);
  const activityEntries = all.slice(-MAX_ACTIVITY).reverse();

  const jobsResult = await listJobs(30, 0).catch(() => ({ jobs: [], hasMore: false }));
  const health = await getHealth().catch(() => ({ healthy: false }));

  const now = Date.now();
  if (now - cachedProjectsAt > PROJECTS_TTL_MS) {
    cachedProjects = await listResearchProjects().catch(() => []);
    cachedProjectsAt = now;
  }

  return {
    ts: new Date().toISOString(),
    activity: { entries: activityEntries },
    jobs: jobsResult,
    health,
    research: { projects: cachedProjects },
  };
}

function encodeSse(event: string, data: unknown): string {
  return `event: ${event}\ndata: ${JSON.stringify(data)}\n\n`;
}

export async function GET(request: NextRequest) {
  const ok = await getSession();
  if (!ok) return NextResponse.json({ error: "Unauthorized" }, { status: 401 });
  const snapshotMode = request.nextUrl.searchParams.get("snapshot");
  if (snapshotMode === "1") {
    try {
      const snapshot = await buildSnapshot();
      return NextResponse.json(snapshot);
    } catch (e) {
      return NextResponse.json({ error: String((e as Error).message) }, { status: 500 });
    }
  }

  const encoder = new TextEncoder();
  let streamTimer: NodeJS.Timeout | null = null;
  let pingTimer: NodeJS.Timeout | null = null;

  const stream = new ReadableStream<Uint8Array>({
    async start(controller) {
      let closed = false;

      const closeAll = () => {
        if (closed) return;
        closed = true;
        if (streamTimer) clearInterval(streamTimer);
        if (pingTimer) clearInterval(pingTimer);
        controller.close();
      };

      request.signal.addEventListener("abort", closeAll);

      const pushSnapshot = async () => {
        if (closed) return;
        try {
          const snapshot = await buildSnapshot();
          controller.enqueue(encoder.encode(encodeSse("snapshot", snapshot)));
        } catch (e) {
          controller.enqueue(
            encoder.encode(
              encodeSse("error", {
                ts: new Date().toISOString(),
                message: String((e as Error).message),
              })
            )
          );
        }
      };

      await pushSnapshot();
      streamTimer = setInterval(pushSnapshot, STREAM_INTERVAL_MS);
      pingTimer = setInterval(() => {
        if (!closed) {
          controller.enqueue(encoder.encode(`: ping ${Date.now()}\n\n`));
        }
      }, PING_INTERVAL_MS);
    },
    cancel() {
      if (streamTimer) clearInterval(streamTimer);
      if (pingTimer) clearInterval(pingTimer);
    },
  });

  return new Response(stream, {
    headers: {
      "Content-Type": "text/event-stream",
      "Cache-Control": "no-cache, no-transform",
      Connection: "keep-alive",
      "X-Accel-Buffering": "no",
    },
  });
}
