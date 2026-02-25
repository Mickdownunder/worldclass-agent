import { NextRequest, NextResponse } from "next/server";
import { getSession } from "@/lib/auth/session";
import { runWorkflow } from "@/lib/operator/actions";

export const dynamic = "force-dynamic";

export async function POST(request: NextRequest) {
  const ok = await getSession();
  if (!ok) return NextResponse.json({ ok: false, error: "Unauthorized" }, { status: 401 });
  try {
    const body = await request.json();
    const workflowId = typeof body.workflow_id === "string" ? body.workflow_id.trim() : "";
    const requestText = typeof body.request === "string" ? body.request : "";
    if (!workflowId) {
      return NextResponse.json({ ok: false, error: "Missing workflow_id" }, { status: 400 });
    }
    const result = await runWorkflow(workflowId, requestText);
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
