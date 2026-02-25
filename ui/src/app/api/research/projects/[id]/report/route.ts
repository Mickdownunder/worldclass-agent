import { NextRequest, NextResponse } from "next/server";
import { getSession } from "@/lib/auth/session";
import { getLatestReportMarkdown } from "@/lib/operator/research";

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
    const markdown = await getLatestReportMarkdown(id);
    if (markdown === null)
      return NextResponse.json({ error: "No report yet" }, { status: 404 });
    return NextResponse.json({ markdown });
  } catch (e) {
    return NextResponse.json(
      { error: String((e as Error).message) },
      { status: 500 }
    );
  }
}
