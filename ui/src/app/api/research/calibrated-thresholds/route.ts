import { NextResponse } from "next/server";
import { getCalibratedThresholds } from "@/lib/operator/research";

export const dynamic = "force-dynamic";

export async function GET() {
  try {
    const thresholds = await getCalibratedThresholds();
    return NextResponse.json(thresholds ?? {});
  } catch (e) {
    return NextResponse.json(
      { error: String((e as Error).message) },
      { status: 500 }
    );
  }
}
