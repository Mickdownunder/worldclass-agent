import { NextResponse } from "next/server";
import { getDecisions, getMemorySummary } from "@/lib/operator/memory";
import { getHealth } from "@/lib/operator/health";
import { getSession } from "@/lib/auth/session";

export const dynamic = "force-dynamic";

export async function GET() {
  const ok = await getSession();
  if (!ok)
    return NextResponse.json({ error: "Unauthorized" }, { status: 401 });

  try {
    const [decisions, mem, health] = await Promise.all([
      getDecisions(20),
      getMemorySummary(),
      getHealth(),
    ]);

    const seen = new Set<string>();
    const latestTrace: typeof decisions = [];
    for (const d of decisions) {
      const phase = d.phase?.toLowerCase();
      if (phase && !seen.has(phase)) {
        seen.add(phase);
        latestTrace.push(d);
      }
    }

    const totals = mem?.totals ?? {};
    const brain = health?.brain ?? null;

    return NextResponse.json({
      latestTrace,
      totalCycles: totals.decisions ?? 0,
      totalReflections: totals.reflections ?? 0,
      avgQuality: totals.avg_quality ?? 0,
      brain,
      ts: Date.now(),
    });
  } catch (e) {
    return NextResponse.json(
      { error: String((e as Error).message) },
      { status: 500 },
    );
  }
}
