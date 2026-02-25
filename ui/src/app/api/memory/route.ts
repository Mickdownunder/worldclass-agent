import { NextResponse } from "next/server";
import { getMemorySummary } from "@/lib/operator/memory";

export const dynamic = "force-dynamic";

export async function GET() {
  try {
    const summary = await getMemorySummary();
    return NextResponse.json(summary ?? { totals: {}, recent_episodes: [], recent_reflections: [], playbooks: [] });
  } catch (e) {
    return NextResponse.json(
      { error: String((e as Error).message) },
      { status: 500 }
    );
  }
}
