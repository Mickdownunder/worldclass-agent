import { NextResponse } from "next/server";
import { readFile } from "fs/promises";
import path from "path";
import { OPERATOR_ROOT } from "@/lib/operator/config";

export const dynamic = "force-dynamic";

const LOG_FILE = path.join(OPERATOR_ROOT, "logs", "agent-activity.jsonl");
const MAX_ENTRIES = 100;

export interface AgentActivityEntry {
  ts: string;
  from: string;
  to: string;
  plan: string;
  request?: string;
  overall?: string;
  recommendation?: string;
  atlas_overall?: string;
  atlas_recommendation?: string;
  run_dir?: string;
}

export async function GET() {
  try {
    const raw = await readFile(LOG_FILE, "utf-8").catch(() => "");
    const lines = raw.split("\n").filter(Boolean);
    const entries: AgentActivityEntry[] = [];
    for (let i = lines.length - 1; i >= 0 && entries.length < MAX_ENTRIES; i--) {
      try {
        const e = JSON.parse(lines[i]) as AgentActivityEntry;
        if (e.ts && e.from && e.to) entries.push(e);
      } catch {
        // skip malformed lines
      }
    }
    return NextResponse.json({ entries });
  } catch (e) {
    return NextResponse.json(
      { error: String((e as Error).message), entries: [] },
      { status: 500 }
    );
  }
}
