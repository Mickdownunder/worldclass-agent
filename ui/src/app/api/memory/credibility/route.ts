import { NextResponse } from "next/server";
import { getSourceCredibility } from "@/lib/operator/memory";

export const dynamic = "force-dynamic";

export async function GET(request: Request) {
  try {
    const { searchParams } = new URL(request.url);
    const limit = Math.min(Number(searchParams.get("limit")) || 50, 100);
    const credibility = await getSourceCredibility(limit);
    return NextResponse.json({ credibility });
  } catch (e) {
    return NextResponse.json(
      { error: String((e as Error).message) },
      { status: 500 }
    );
  }
}
