import { NextResponse } from "next/server";
import { readFile } from "fs/promises";
import path from "path";
import { OPERATOR_ROOT } from "@/lib/operator/config";
import { listJobs } from "@/lib/operator/jobs";

export const dynamic = "force-dynamic";

const AUDIT_LOG = path.join(OPERATOR_ROOT, "logs", "ui-audit.log");

export async function GET() {
  const events: Array<{ ts: string; type: string; payload: string }> = [];
  try {
    const raw = await readFile(AUDIT_LOG, "utf-8");
    const lines = raw.trim().split("\n").slice(-50).reverse();
    for (const line of lines) {
      const parts = line.split(" | ");
      if (parts.length >= 4) {
        events.push({
          ts: parts[0],
          type: parts[1],
          payload: parts.slice(2).join(" | "),
        });
      }
    }
  } catch {
    //
  }
  const { jobs } = await listJobs(10, 0);
  const jobEvents = jobs.map((j) => ({
    ts: j.created_at ?? "",
    type: "job",
    payload: `${j.id} | ${j.workflow_id} | ${j.status}`,
  }));
  const combined = [...jobEvents, ...events]
    .filter((e) => e.ts)
    .sort((a, b) => b.ts.localeCompare(a.ts))
    .slice(0, 40);
  return NextResponse.json({ events: combined });
}
