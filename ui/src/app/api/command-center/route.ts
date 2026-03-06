import { NextResponse } from "next/server";
import { getSession } from "@/lib/auth/session";
import { executeCommandCenterAction, listCommandCenter } from "@/lib/operator/command-center";

export const dynamic = "force-dynamic";

export async function GET() {
  const authed = await getSession();
  if (!authed) {
    return NextResponse.json({ error: "unauthorized" }, { status: 401 });
  }
  try {
    return NextResponse.json(await listCommandCenter());
  } catch (error) {
    return NextResponse.json({ error: String((error as Error).message) }, { status: 500 });
  }
}

export async function POST(request: Request) {
  const authed = await getSession();
  if (!authed) {
    return NextResponse.json({ error: "unauthorized" }, { status: 401 });
  }

  try {
    const body = await request.json();
    const result = await executeCommandCenterAction({
      action: body.action,
      missionId: typeof body.missionId === "string" ? body.missionId : undefined,
      objective: typeof body.objective === "string" ? body.objective : undefined,
      requestText: typeof body.requestText === "string" ? body.requestText : undefined,
      reason: typeof body.reason === "string" ? body.reason : undefined,
      execute: typeof body.execute === "boolean" ? body.execute : undefined,
    });

    if (!result.ok) {
      return NextResponse.json(result, { status: 400 });
    }
    return NextResponse.json(result);
  } catch (error) {
    return NextResponse.json({ ok: false, error: String((error as Error).message) }, { status: 500 });
  }
}
