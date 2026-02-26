import { NextRequest, NextResponse } from "next/server";
import { getSession } from "@/lib/auth/session";
import { getResearchProject, deleteResearchProject } from "@/lib/operator/research";

export const dynamic = "force-dynamic";

export async function GET(
  _request: NextRequest,
  { params }: { params: Promise<{ id: string }> }
) {
  const ok = await getSession();
  if (!ok) return NextResponse.json({ error: "Unauthorized" }, { status: 401 });
  const id = (await params).id;
  if (!id) return NextResponse.json({ error: "Missing id" }, { status: 400 });
  try {
    const project = await getResearchProject(id);
    if (!project) return NextResponse.json({ error: "Not found" }, { status: 404 });
    return NextResponse.json(project);
  } catch (e) {
    return NextResponse.json(
      { error: String((e as Error).message) },
      { status: 500 }
    );
  }
}

export async function DELETE(
  _request: NextRequest,
  { params }: { params: Promise<{ id: string }> }
) {
  const ok = await getSession();
  if (!ok) return NextResponse.json({ error: "Unauthorized" }, { status: 401 });
  const id = (await params).id;
  if (!id) return NextResponse.json({ error: "Missing id" }, { status: 400 });
  try {
    const project = await getResearchProject(id);
    if (!project) return NextResponse.json({ error: "Not found" }, { status: 404 });
    await deleteResearchProject(id);
    return new NextResponse(null, { status: 204 });
  } catch (e) {
    return NextResponse.json(
      { error: String((e as Error).message) },
      { status: 500 }
    );
  }
}
