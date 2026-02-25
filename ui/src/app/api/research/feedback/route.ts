import { NextRequest, NextResponse } from "next/server";
import { getSession } from "@/lib/auth/session";
import { OPERATOR_ROOT } from "@/lib/operator/config";
import { spawn } from "child_process";
import path from "path";

export const dynamic = "force-dynamic";

const VALID_TYPES = ["dig_deeper", "wrong", "excellent", "ignore", "redirect"];

export async function POST(request: NextRequest) {
  const ok = await getSession();
  if (!ok) return NextResponse.json({ ok: false, error: "Unauthorized" }, { status: 401 });
  try {
    const body = await request.json();
    const projectId = typeof body.project_id === "string" ? body.project_id.trim() : "";
    const type = typeof body.type === "string" ? body.type.trim().toLowerCase() : "";
    const comment = typeof body.comment === "string" ? body.comment.trim() : "";

    if (!projectId || !type) {
      return NextResponse.json(
        { ok: false, error: "Missing project_id or type" },
        { status: 400 }
      );
    }
    if (!VALID_TYPES.includes(type)) {
      return NextResponse.json(
        { ok: false, error: `Invalid type. Use one of: ${VALID_TYPES.join(", ")}` },
        { status: 400 }
      );
    }

    const script = path.join(OPERATOR_ROOT, "tools", "research_feedback.py");
    const args = comment ? [projectId, type, comment] : [projectId, type];

    const result = await new Promise<{ ok: boolean; error?: string }>((resolve) => {
      const proc = spawn("python3", [script, ...args], {
        cwd: OPERATOR_ROOT,
      });
      let stdout = "";
      let stderr = "";
      proc.stdout?.on("data", (d) => { stdout += d.toString(); });
      proc.stderr?.on("data", (d) => { stderr += d.toString(); });
      proc.on("close", (code) => {
        if (code !== 0) {
          resolve({ ok: false, error: stderr || stdout || `Exit ${code}` });
          return;
        }
        try {
          const data = JSON.parse(stdout);
          resolve(data.ok ? { ok: true } : { ok: false, error: "Script returned not ok" });
        } catch {
          resolve({ ok: true });
        }
      });
    });

    if (!result.ok) {
      return NextResponse.json(result, { status: 400 });
    }
    return NextResponse.json({ ok: true });
  } catch (e) {
    return NextResponse.json(
      { ok: false, error: String((e as Error).message) },
      { status: 500 }
    );
  }
}
