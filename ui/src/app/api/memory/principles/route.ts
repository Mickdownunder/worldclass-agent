import { NextResponse } from "next/server";
import { getPrinciples } from "@/lib/operator/memory";

export const dynamic = "force-dynamic";

export async function GET(request: Request) {
  try {
    const { searchParams } = new URL(request.url);
    const limit = Math.min(Number(searchParams.get("limit")) || 50, 100);
    const domain = searchParams.get("domain") ?? undefined;
    const principles = await getPrinciples(limit, domain);
    return NextResponse.json({ principles });
  } catch (e) {
    return NextResponse.json(
      { error: String((e as Error).message) },
      { status: 500 }
    );
  }
}
