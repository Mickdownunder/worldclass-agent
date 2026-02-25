import { NextResponse } from "next/server";
import { getSession } from "@/lib/auth/session";
import { ALLOWED_WORKFLOWS } from "@/lib/operator/actions";

export const dynamic = "force-dynamic";

export async function GET() {
  const ok = await getSession();
  if (!ok) return NextResponse.json({ error: "Unauthorized" }, { status: 401 });
  return NextResponse.json({ workflows: Array.from(ALLOWED_WORKFLOWS).sort() });
}
