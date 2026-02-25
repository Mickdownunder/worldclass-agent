import { NextRequest, NextResponse } from "next/server";
import { authConfig } from "@/lib/auth/config";
import { setSession, clearSession } from "@/lib/auth/session";

export const dynamic = "force-dynamic";

export async function POST(request: NextRequest) {
  try {
    const body = await request.json();
    const password = typeof body.password === "string" ? body.password : "";
    if (!password) {
      await clearSession();
      return NextResponse.json({ ok: false, error: "Missing password" }, { status: 400 });
    }
    if (!authConfig.checkPassword(password)) {
      await clearSession();
      return NextResponse.json({ ok: false, error: "Invalid password" }, { status: 401 });
    }
    await setSession();
    return NextResponse.json({ ok: true });
  } catch (e) {
    return NextResponse.json(
      { ok: false, error: String((e as Error).message) },
      { status: 500 }
    );
  }
}
