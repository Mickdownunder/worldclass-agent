import { NextRequest, NextResponse } from "next/server";
import { getSession } from "@/lib/auth/session";
import { retryJob } from "@/lib/operator/actions";

export const dynamic = "force-dynamic";

export async function POST(request: NextRequest) {
  const ok = await getSession();
  if (!ok) return NextResponse.json({ ok: false, error: "Unauthorized" }, { status: 401 });
  try {
    const body = await request.json();
    const jobId = typeof body.job_id === "string" ? body.job_id.trim() : "";
    if (!jobId) {
      return NextResponse.json({ ok: false, error: "Missing job_id" }, { status: 400 });
    }
    const result = await retryJob(jobId);
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
