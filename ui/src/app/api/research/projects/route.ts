import { NextRequest, NextResponse } from "next/server";
import { getSession } from "@/lib/auth/session";
import { listResearchProjects } from "@/lib/operator/research";
import { runWorkflow, runResearchInitAndCycleUntilDone } from "@/lib/operator/actions";

export const dynamic = "force-dynamic";

export async function GET() {
  const ok = await getSession();
  if (!ok) return NextResponse.json({ error: "Unauthorized" }, { status: 401 });
  try {
    const projects = await listResearchProjects();
    return NextResponse.json({ projects });
  } catch (e) {
    return NextResponse.json(
      { error: String((e as Error).message) },
      { status: 500 }
    );
  }
}

export async function POST(request: NextRequest) {
  const ok = await getSession();
  if (!ok) return NextResponse.json({ error: "Unauthorized" }, { status: 401 });
  try {
    const body = await request.json();
    const question = typeof body.question === "string" ? body.question.trim() : "";
    if (!question) {
      return NextResponse.json(
        { ok: false, error: "question ist erforderlich" },
        { status: 400 }
      );
    }
    const runUntilDone = body.run_until_done !== false;
    const result = runUntilDone
      ? await runResearchInitAndCycleUntilDone(question)
      : await runWorkflow("research-init", question);
    if (!result.ok) {
      return NextResponse.json(
        { ok: false, error: result.error ?? "Workflow fehlgeschlagen" },
        { status: 400 }
      );
    }
    if (runUntilDone && "projectId" in result) {
      return NextResponse.json({
        ok: true,
        jobId: result.jobId,
        projectId: result.projectId,
        message: "Projekt angelegt. Alle Phasen laufen automatisch – Report erscheint, wenn fertig.",
      });
    }
    return NextResponse.json({
      ok: true,
      jobId: result.jobId,
      message: "Research-Projekt wird erstellt (Job läuft).",
    });
  } catch (e) {
    return NextResponse.json(
      { ok: false, error: String((e as Error).message) },
      { status: 500 }
    );
  }
}
