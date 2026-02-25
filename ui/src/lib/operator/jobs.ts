import { readFile, readdir, rm } from "fs/promises";
import path from "path";
import { OPERATOR_ROOT } from "./config";

const JOBS_PATH = path.join(OPERATOR_ROOT, "jobs");

export interface JobSummary {
  id: string;
  workflow_id: string;
  status: string;
  request?: string;
  created_at?: string;
  started_at?: string;
  finished_at?: string;
  duration_s?: number;
  error?: string;
  attempt?: number;
}

export interface ListJobsResult {
  jobs: JobSummary[];
  hasMore: boolean;
}

const VALID_STATUS_FILTERS = new Set(["DONE", "FAILED", "RUNNING", "CREATED"]);

export async function listJobs(
  limit = 20,
  offset = 0,
  statusFilter?: string
): Promise<ListJobsResult> {
  const jobs: JobSummary[] = [];
  if (!JOBS_PATH) return { jobs, hasMore: false };
  const statusMatch =
    statusFilter && VALID_STATUS_FILTERS.has(statusFilter)
      ? statusFilter
      : undefined;
  try {
    const dayDirs = await readdir(JOBS_PATH, { withFileTypes: true });
    const dirs = dayDirs
      .filter((d) => d.isDirectory())
      .map((d) => d.name)
      .sort()
      .reverse();
    let skipped = 0;
    for (const day of dirs) {
      const dayPath = path.join(JOBS_PATH, day);
      const entries = await readdir(dayPath, { withFileTypes: true });
      for (const ent of entries) {
        if (!ent.isDirectory()) continue;
        const jobPath = path.join(dayPath, ent.name, "job.json");
        try {
          const raw = await readFile(jobPath, "utf-8");
          const j = JSON.parse(raw) as JobSummary;
          if (statusMatch != null && j.status !== statusMatch) continue;
          if (skipped < offset) {
            skipped++;
            continue;
          }
          jobs.push(j);
          if (jobs.length >= limit + 1) {
            return { jobs: jobs.slice(0, limit), hasMore: true };
          }
        } catch {
          // skip invalid/missing job.json
        }
      }
    }
  } catch {
    // jobs dir missing or unreadable
  }
  return { jobs, hasMore: false };
}

export async function getJobDir(jobId: string): Promise<string | null> {
  try {
    const dayDirs = await readdir(JOBS_PATH, { withFileTypes: true });
    const dirs = dayDirs.filter((d) => d.isDirectory()).map((d) => d.name).sort().reverse();
    for (const day of dirs) {
      const candidate = path.join(JOBS_PATH, day, jobId);
      const jobJson = path.join(candidate, "job.json");
      try {
        await readFile(jobJson, "utf-8");
        return candidate;
      } catch {
        continue;
      }
    }
  } catch {
    //
  }
  return null;
}

export async function deleteJob(jobId: string): Promise<boolean> {
  const dir = await getJobDir(jobId);
  if (!dir) return false;
  try {
    await rm(dir, { recursive: true });
    return true;
  } catch {
    return false;
  }
}

export async function getJob(
  jobId: string
): Promise<(JobSummary & { log?: string; artifacts?: string[] }) | null> {
  try {
    const dayDirs = await readdir(JOBS_PATH, { withFileTypes: true });
    const dirs = dayDirs.filter((d) => d.isDirectory()).map((d) => d.name).sort().reverse();
    for (const day of dirs) {
      const candidate = path.join(JOBS_PATH, day, jobId);
      const jobJson = path.join(candidate, "job.json");
      try {
        const raw = await readFile(jobJson, "utf-8");
        const j = JSON.parse(raw) as JobSummary & { log?: string; artifacts?: string[] };
        const logPath = path.join(candidate, "log.txt");
        try {
          j.log = await readFile(logPath, "utf-8");
        } catch {
          // no log
        }
        const artifactsDir = path.join(candidate, "artifacts");
        try {
          const files = await readdir(artifactsDir);
          j.artifacts = files.filter((f) => !f.startsWith("."));
        } catch {
          j.artifacts = [];
        }
        return j;
      } catch {
        continue;
      }
    }
  } catch {
    //
  }
  return null;
}
