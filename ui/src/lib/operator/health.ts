import { execFile } from "child_process";
import { promisify } from "util";
import path from "path";
import { OPERATOR_ROOT } from "./config";

const exec = promisify(execFile);
const OP_BIN = path.join(OPERATOR_ROOT, "bin", "op");

export interface BrainProcessGroup {
  count: number;
  max_elapsed_sec?: number;
  stuck?: boolean;
}

export interface BrainStatus {
  cycle?: BrainProcessGroup;
  reflect?: BrainProcessGroup;
}

export interface HealthResult {
  disk_used_pct?: number;
  disk_ok?: boolean;
  load_1m?: number;
  load_ok?: boolean;
  jobs_total?: number;
  jobs_failed?: number;
  jobs_running?: number;
  recent_failures?: string[];
  workflows_available?: number;
  policy?: string;
  memory?: { episodes?: number; decisions?: number; reflections?: number; avg_quality?: number };
  avg_quality?: number;
  brain?: BrainStatus;
  healthy?: boolean;
}

export async function getHealth(): Promise<HealthResult> {
  try {
    const { stdout } = await exec(OP_BIN, ["healthcheck"], {
      timeout: 15000,
      env: { ...process.env },
    });
    return JSON.parse(stdout) as HealthResult;
  } catch (e) {
    return {
      healthy: false,
      recent_failures: [String((e as Error).message)],
    };
  }
}
