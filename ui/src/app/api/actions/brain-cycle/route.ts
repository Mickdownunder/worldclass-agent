import { NextRequest, NextResponse } from "next/server";
import { getSession } from "@/lib/auth/session";
import { runBrainCycle } from "@/lib/operator/actions";

export const dynamic = "force-dynamic";

export async function POST(request: NextRequest) {
  const ok = await getSession();
  if (!ok) return NextResponse.json({ ok: false, error: "Unauthorized" }, { status: 401 });
  try {
    const body = await request.json().catch(() => ({}));
    const goal = typeof body.goal === "string" ? body.goal : "Decide and execute the most impactful next action";
    const result = await runBrainCycle(goal);
    if (!result.ok) {
      return NextResponse.json(result, { status: 400 });
    }
    return NextResponse.json(result);
  } catch (e) {
    return NextResponse.json(
      { ok: false, error: String((e as Error).message) },
      { status: 500 }
    );
  }
}
