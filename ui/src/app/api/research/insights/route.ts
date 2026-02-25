import { NextResponse } from "next/server";
import { getSession } from "@/lib/auth/session";
import { getCrossDomainInsights } from "@/lib/operator/memory";

export const dynamic = "force-dynamic";

export async function GET() {
  const ok = await getSession();
  if (!ok) return NextResponse.json({ error: "Unauthorized" }, { status: 401 });
  try {
    const insights = await getCrossDomainInsights(50);
    return NextResponse.json({ insights });
  } catch (e) {
    return NextResponse.json(
      { error: String((e as Error).message) },
      { status: 500 }
    );
  }
}
