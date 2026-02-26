import { NextResponse } from "next/server";
import { getEntities } from "@/lib/operator/memory";

export const dynamic = "force-dynamic";

export async function GET(request: Request) {
  try {
    const { searchParams } = new URL(request.url);
    const type = searchParams.get("type") ?? undefined;
    const project = searchParams.get("project") ?? undefined;
    const { entities, relations } = await getEntities({ type, project });
    return NextResponse.json({ entities, relations });
  } catch (e) {
    return NextResponse.json(
      { error: String((e as Error).message) },
      { status: 500 }
    );
  }
}
