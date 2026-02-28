import { NextResponse } from "next/server";
import { readFile } from "fs/promises";
import path from "path";
import { getSession } from "@/lib/auth/session";
import { getResearchProject } from "@/lib/operator/research";
import { runWorkflow } from "@/lib/operator/actions";
import { OPERATOR_ROOT } from "@/lib/operator/config";

export const dynamic = "force-dynamic";

const RESEARCH_ROOT = path.join(OPERATOR_ROOT, "research");
const PROJECT_ID_RE = /^proj-[a-zA-Z0-9_-]+$/;

/** Return progress.json alive flag if readable. */
async function isCycleRunning(projectId: string): Promise<boolean> {
  if (!PROJECT_ID_RE.test(projectId)) return false;
  const projPath = path.join(RESEARCH_ROOT, projectId);
  const progressPath = path.join(projPath, "progress.json");
  try {
    const raw = await readFile(progressPath, "utf8");
    const data = JSON.parse(raw) as { alive?: boolean };
    return data.alive === true;
  } catch {
    return false;
  }
}

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
    if (project.status === "done") {
      return NextResponse.json(
        { ok: false, error: "Projekt ist bereits abgeschlossen." },
        { status: 400 }
      );
    }
    if (await isCycleRunning(id)) {
      return NextResponse.json(
        { ok: false, error: "Ein Cycle läuft bereits für dieses Projekt." },
        { status: 409 }
      );
    }
    const result = await runWorkflow("research-cycle", id);
    if (!result.ok) {
      return NextResponse.json(
        { ok: false, error: result.error ?? "Cycle fehlgeschlagen" },
        { status: 400 }
      );
    }
    return NextResponse.json({
      ok: true,
      jobId: result.jobId,
      message: "Nächste Phase wird gestartet (Job läuft).",
    });
  } catch (e) {
    return NextResponse.json(
      { ok: false, error: String((e as Error).message) },
      { status: 500 }
    );
  }
}
