import { NextResponse } from "next/server";
import { getSession } from "@/lib/auth/session";
import { listResearchProjects } from "@/lib/operator/research";

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
