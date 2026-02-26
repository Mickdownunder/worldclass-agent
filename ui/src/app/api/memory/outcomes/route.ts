import { NextResponse } from "next/server";
import { getProjectOutcomes } from "@/lib/operator/memory";

export const dynamic = "force-dynamic";

export async function GET(request: Request) {
  try {
    const { searchParams } = new URL(request.url);
    const limit = Math.min(Number(searchParams.get("limit")) || 100, 200);
    const { outcomes, total } = await getProjectOutcomes(limit);
    return NextResponse.json({ outcomes, total });
  } catch (e) {
    return NextResponse.json(
      { error: String((e as Error).message) },
      { status: 500 }
    );
  }
}
