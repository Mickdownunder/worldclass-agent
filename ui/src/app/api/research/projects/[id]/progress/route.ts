import { NextRequest, NextResponse } from "next/server";
import { getSession } from "@/lib/auth/session";
import { readFile } from "fs/promises";
import path from "path";
import { OPERATOR_ROOT } from "@/lib/operator/config";

export const dynamic = "force-dynamic";

const RESEARCH_ROOT = path.join(OPERATOR_ROOT, "research");

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
    const progressPath = path.join(projPath, "progress.json");
    
    let progressData: any = {};
    try {
      const raw = await readFile(progressPath, "utf8");
      progressData = JSON.parse(raw);
    } catch {
      // If progress.json doesn't exist or is invalid, return default inactive state
      return NextResponse.json({ is_running: false, data: null });
    }

    // Compute is_running based on heartbeat freshness (< 30s)
    let is_running = false;
    if (progressData.alive && progressData.heartbeat) {
      const heartbeatTime = new Date(progressData.heartbeat).getTime();
      const now = Date.now();
      if (!isNaN(heartbeatTime) && (now - heartbeatTime) < 30000) {
        is_running = true;
      }
    }

    return NextResponse.json({ is_running, data: progressData });
  } catch (e) {
    return NextResponse.json(
      { error: String((e as Error).message) },
      { status: 500 }
    );
  }
}