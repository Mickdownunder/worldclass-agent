import { NextResponse } from "next/server";
import { getSession } from "@/lib/auth/session";
import { getResearchProject, getAllReports } from "@/lib/operator/research";

export const dynamic = "force-dynamic";

export async function GET(
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
    const reports = await getAllReports(id);
    return NextResponse.json({ reports });
  } catch (e) {
    return NextResponse.json(
      { error: String((e as Error).message) },
      { status: 500 }
    );
  }
}
