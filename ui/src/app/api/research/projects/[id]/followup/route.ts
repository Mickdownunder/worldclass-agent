import { NextResponse } from "next/server";
import { getSession } from "@/lib/auth/session";
import { getResearchProject } from "@/lib/operator/research";
import { OPERATOR_ROOT } from "@/lib/operator/config";
import { spawn } from "child_process";
import path from "path";

export const dynamic = "force-dynamic";

const SCRIPT = path.join(OPERATOR_ROOT, "tools", "research_auto_followup.py");

export async function POST(
  _request: Request,
  { params }: { params: Promise<{ id: string }> }
) {
  const ok = await getSession();
  if (!ok) return NextResponse.json({ error: "Unauthorized" }, { status: 401 });
  const id = (await params).id;
  if (!id) return NextResponse.json({ error: "id fehlt" }, { status: 400 });
  try {
    const project = await getResearchProject(id);
    if (!project)
      return NextResponse.json({ error: "Projekt nicht gefunden" }, { status: 404 });
    if (project.status !== "done") {
      return NextResponse.json(
        { ok: false, error: "Nur bei abgeschlossenen Projekten (done) möglich." },
        { status: 400 }
      );
    }

    const result = await new Promise<{ stdout: string; stderr: string; code: number | null }>(
      (resolve) => {
        let stdout = "";
        let stderr = "";
        const proc = spawn("python3", [SCRIPT, id], {
          cwd: OPERATOR_ROOT,
          env: { ...process.env, RESEARCH_MAX_FOLLOWUPS: "3" },
        });
        proc.stdout?.on("data", (d) => { stdout += d.toString(); });
        proc.stderr?.on("data", (d) => { stderr += d.toString(); });
        proc.on("close", (code) => resolve({ stdout, stderr, code }));
        proc.on("error", (err) => {
          stderr += err.message;
          resolve({ stdout, stderr, code: 1 });
        });
      }
    );

    const log = (result.stdout + "\n" + result.stderr).trim();
    if (result.code !== 0) {
      return NextResponse.json({
        ok: false,
        error: result.stderr || result.stdout || "Script fehlgeschlagen",
        log,
      }, { status: 400 });
    }
    return NextResponse.json({ ok: true, log });
  } catch (e) {
    return NextResponse.json(
      { ok: false, error: String((e as Error).message) },
      { status: 500 }
    );
  }
}
