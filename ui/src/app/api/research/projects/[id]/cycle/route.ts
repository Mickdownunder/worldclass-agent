import { NextResponse } from "next/server";
import { getSession } from "@/lib/auth/session";
import { getResearchProject } from "@/lib/operator/research";
import { runWorkflow } from "@/lib/operator/actions";

export const dynamic = "force-dynamic";

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
