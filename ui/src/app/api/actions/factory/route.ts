import { NextResponse } from "next/server";
import { getSession } from "@/lib/auth/session";
import { runFactoryCycle } from "@/lib/operator/actions";

export const dynamic = "force-dynamic";

export async function POST() {
  const ok = await getSession();
  if (!ok) return NextResponse.json({ ok: false, error: "Unauthorized" }, { status: 401 });
  try {
    const result = await runFactoryCycle();
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
