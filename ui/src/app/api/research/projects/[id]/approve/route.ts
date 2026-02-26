import { NextRequest, NextResponse } from "next/server";
import { getSession } from "@/lib/auth/session";
import { getResearchProject, approveProject } from "@/lib/operator/research";

export const dynamic = "force-dynamic";

export async function POST(
  request: NextRequest,
  { params }: { params: Promise<{ id: string }> }
) {
  const ok = await getSession();
  if (!ok) return NextResponse.json({ error: "Unauthorized" }, { status: 401 });
  const id = (await params).id;
  if (!id) return NextResponse.json({ error: "Missing id" }, { status: 400 });
  try {
    const project = await getResearchProject(id);
    if (!project) return NextResponse.json({ error: "Not found" }, { status: 404 });
    if (project.status !== "pending_review") {
      return NextResponse.json(
        { error: "Project is not in pending_review" },
        { status: 400 }
      );
    }
    const body = await request.json().catch(() => ({}));
    const action = body.action === "reject" ? "reject" : "approve";
    const result = await approveProject(id, action);
    return NextResponse.json(result);
  } catch (e) {
    return NextResponse.json(
      { error: String((e as Error).message) },
      { status: 500 }
    );
  }
}
