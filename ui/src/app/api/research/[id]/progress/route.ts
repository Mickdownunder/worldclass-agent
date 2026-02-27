import { NextRequest, NextResponse } from "next/server";

export const dynamic = "force-dynamic";

export async function GET(
  request: NextRequest,
  { params }: { params: Promise<{ id: string }> }
) {
  const id = (await params).id;
  if (!id) return NextResponse.json({ error: "Missing id" }, { status: 400 });

  const target = new URL(`/api/research/projects/${encodeURIComponent(id)}/progress`, request.url);
  return NextResponse.redirect(target, { status: 307 });
}
