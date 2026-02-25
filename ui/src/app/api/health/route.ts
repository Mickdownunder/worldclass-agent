import { NextResponse } from "next/server";
import { getHealth } from "@/lib/operator/health";

export const dynamic = "force-dynamic";

export async function GET() {
  try {
    const health = await getHealth();
    return NextResponse.json(health);
  } catch (e) {
    return NextResponse.json(
      { healthy: false, error: String((e as Error).message) },
      { status: 500 }
    );
  }
}
