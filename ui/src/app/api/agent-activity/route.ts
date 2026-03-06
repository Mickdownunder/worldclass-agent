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
  command?: string;
  overall?: string;
  recommendation?: string;
  atlas_overall?: string;
  atlas_recommendation?: string;
  run_dir?: string;
}

/** Parse JSONL: one object per line (compact) or multi-line pretty-printed objects */
function parseJsonl(raw: string): AgentActivityEntry[] {
  const entries: AgentActivityEntry[] = [];
  const lines = raw.split("\n");
  let buffer = "";
  let depth = 0;
  for (const line of lines) {
    buffer += (buffer ? "\n" : "") + line;
    for (const c of line) {
      if (c === "{") depth++;
      else if (c === "}") depth--;
    }
    if (depth === 0 && buffer.trim()) {
      try {
        const e = JSON.parse(buffer) as AgentActivityEntry;
        if (e.ts && e.from && e.to) entries.push(e);
      } catch {
        // skip malformed
      }
      buffer = "";
    }
  }
  if (buffer.trim()) {
    try {
      const e = JSON.parse(buffer) as AgentActivityEntry;
      if (e.ts && e.from && e.to) entries.push(e);
    } catch {
      //
    }
  }
  return entries;
}

export async function GET() {
  try {
    const raw = await readFile(LOG_FILE, "utf-8").catch(() => "");
    const all = parseJsonl(raw);
    const entries = all.slice(-MAX_ENTRIES).reverse();
    return NextResponse.json({ entries });
  } catch (e) {
    return NextResponse.json(
      { error: String((e as Error).message), entries: [] },
      { status: 500 }
    );
  }
}
