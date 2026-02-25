import { execFile } from "child_process";
import { promisify } from "util";
import path from "path";
import { OPERATOR_ROOT } from "./config";

const exec = promisify(execFile);
const BRAIN_BIN = path.join(OPERATOR_ROOT, "bin", "brain");

export interface MemorySummary {
  totals: { episodes: number; decisions: number; reflections: number; avg_quality: number };
  recent_episodes: Array<{ kind: string; content: string; ts: string }>;
  recent_reflections: Array<{ job_id: string; quality: number; learnings?: string; ts: string }>;
  playbooks: Array<{ domain: string; strategy: string; success_rate: number }>;
}

export async function getMemorySummary(): Promise<MemorySummary | null> {
  try {
    const { stdout } = await exec(BRAIN_BIN, ["memory"], {
      timeout: 10000,
      env: { ...process.env },
    });
    return JSON.parse(stdout) as MemorySummary;
  } catch {
    return null;
  }
}

export interface CrossLinkInsight {
  id: string;
  finding_a_id?: string;
  finding_b_id?: string;
  project_a?: string;
  project_b?: string;
  similarity?: number;
  ts?: string;
}

export async function getCrossDomainInsights(
  limit = 50
): Promise<CrossLinkInsight[]> {
  try {
    const { stdout } = await exec(BRAIN_BIN, ["cross-links", "--limit", String(limit)], {
      timeout: 10000,
      env: { ...process.env },
    });
    const data = JSON.parse(stdout) as { insights?: CrossLinkInsight[] };
    return data.insights ?? [];
  } catch {
    return [];
  }
}
