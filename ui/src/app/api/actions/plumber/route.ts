import { NextRequest, NextResponse } from "next/server";
import { exec } from "child_process";
import { promisify } from "util";
import { getSession } from "@/lib/auth/session";

const run = promisify(exec);
const BRAIN = process.env.OPERATOR_ROOT
  ? `${process.env.OPERATOR_ROOT}/bin/brain`
  : `${process.env.HOME || "/root"}/operator/bin/brain`;

export const dynamic = "force-dynamic";

export async function POST(req: NextRequest) {
  const ok = await getSession();
  if (!ok)
    return NextResponse.json({ ok: false, error: "Unauthorized" }, { status: 401 });

  const body = await req.json().catch(() => ({}));
  const governance = body.governance ?? 2;
  const target = body.target ?? "";

  const args = ["plumber", "--governance", String(governance)];
  if (target) args.push("--target", target);

  try {
    const { stdout, stderr } = await run(
      `${BRAIN} ${args.join(" ")}`,
      { timeout: 30_000 },
    );
    const report = JSON.parse(stdout);
    return NextResponse.json({ ok: true, report });
  } catch (e: unknown) {
    const msg = e instanceof Error ? e.message : String(e);
    return NextResponse.json({ ok: false, error: msg }, { status: 500 });
  }
}

export async function GET(req: NextRequest) {
  const ok = await getSession();
  if (!ok)
    return NextResponse.json({ ok: false, error: "Unauthorized" }, { status: 401 });

  const { searchParams } = new URL(req.url);
  const view = searchParams.get("view");

  try {
    if (view === "fingerprints") {
      const { stdout } = await run(`${BRAIN} plumber --fingerprints`, { timeout: 10_000 });
      return NextResponse.json({ ok: true, fingerprints: JSON.parse(stdout) });
    }

    const { stdout } = await run(`${BRAIN} plumber --list-patches`, { timeout: 10_000 });
    const data = JSON.parse(stdout);
    return NextResponse.json({ ok: true, ...data });
  } catch (e: unknown) {
    const msg = e instanceof Error ? e.message : String(e);
    return NextResponse.json({ ok: false, error: msg }, { status: 500 });
  }
}
