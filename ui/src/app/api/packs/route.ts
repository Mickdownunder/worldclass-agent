import { NextResponse } from "next/server";
import { listPacks } from "@/lib/operator/packs";

export const dynamic = "force-dynamic";

export async function GET() {
  try {
    const packs = await listPacks();
    return NextResponse.json(packs);
  } catch (e) {
    return NextResponse.json(
      { error: String((e as Error).message) },
      { status: 500 }
    );
  }
}
