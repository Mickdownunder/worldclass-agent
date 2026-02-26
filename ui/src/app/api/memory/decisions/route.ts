import { NextResponse } from "next/server";
import { getDecisions } from "@/lib/operator/memory";

export const dynamic = "force-dynamic";

export async function GET(request: Request) {
  try {
    const { searchParams } = new URL(request.url);
    const limit = Math.min(Number(searchParams.get("limit")) || 30, 100);
    const decisions = await getDecisions(limit);
    return NextResponse.json({ decisions });
  } catch (e) {
    return NextResponse.json(
      { error: String((e as Error).message) },
      { status: 500 }
    );
  }
}
