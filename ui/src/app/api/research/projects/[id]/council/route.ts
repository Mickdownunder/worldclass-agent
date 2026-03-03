import { NextRequest, NextResponse } from "next/server";
import { getSession } from "@/lib/auth/session";
import { readFile } from "fs/promises";
import path from "path";
import { OPERATOR_ROOT } from "@/lib/operator/config";

export const dynamic = "force-dynamic";

const RESEARCH_ROOT = path.join(OPERATOR_ROOT, "research");
const PROJECT_ID_RE = /^proj-[a-zA-Z0-9_-]+$/;

function safeProjectPath(projectId: string): string {
  if (!PROJECT_ID_RE.test(projectId)) {
    throw new Error("Invalid project ID");
  }
  const resolved = path.resolve(RESEARCH_ROOT, projectId);
  if (!resolved.startsWith(RESEARCH_ROOT + path.sep)) {
    throw new Error("Invalid project path");
  }
  return resolved;
}

/** GET council log + result (brain_injected, brain_error) for project. */
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
    let log = "";
    let brainInjected: boolean | undefined;
    let brainError: string | null = null;

    try {
      log = await readFile(path.join(projPath, "council.log"), "utf8");
    } catch {
      // no council log
    }

    try {
      const raw = await readFile(
        path.join(projPath, "council_result.json"),
        "utf8"
      );
      const result = JSON.parse(raw) as {
        brain_injected?: boolean;
        brain_error?: string | null;
      };
      brainInjected = result.brain_injected;
      brainError = result.brain_error ?? null;
    } catch {
      // no council_result.json
    }

    return NextResponse.json({
      log,
      brainInjected,
      brainError,
    });
  } catch (e) {
    return NextResponse.json(
      { error: String((e as Error).message) },
      { status: 500 }
    );
  }
}
