import { NextResponse } from "next/server";
import { execFile } from "child_process";
import { promisify } from "util";
import path from "path";

const exec = promisify(execFile);
const BRAIN_BIN = path.join(process.env.OPERATOR_ROOT || path.join(process.env.HOME || "", "operator"), "bin", "brain");

export async function GET(request: Request) {
  try {
    const { searchParams } = new URL(request.url);
    const limit = searchParams.get("limit") || "50";
    
    const { stdout } = await exec(BRAIN_BIN, ["utility", "--limit", limit], {
      timeout: 10000,
      env: { ...process.env },
    });
    
    return NextResponse.json(JSON.parse(stdout));
  } catch (error: any) {
    return NextResponse.json({ error: error.message }, { status: 500 });
  }
}
