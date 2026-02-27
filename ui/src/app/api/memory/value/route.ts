import { NextResponse } from "next/server";
import { getMemoryValueScore } from "@/lib/operator/memory";

export const dynamic = "force-dynamic";

export async function GET() {
  try {
    const score = await getMemoryValueScore();
    return NextResponse.json(score ?? { memory_value: null, applied_avg: null, fallback_avg: null, applied_count: 0, fallback_count: 0 });
  } catch (e) {
    return NextResponse.json(
      { error: String((e as Error).message) },
      { status: 500 }
    );
  }
}
