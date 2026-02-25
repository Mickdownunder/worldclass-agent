import { readdir, readFile } from "fs/promises";
import path from "path";
import { OPERATOR_ROOT } from "./config";

const RESEARCH_ROOT = path.join(OPERATOR_ROOT, "research");

const PROJECT_ID_RE = /^proj-[a-zA-Z0-9_-]+$/;

function safeProjectPath(projectId: string): string {
  if (!PROJECT_ID_RE.test(projectId)) {
    throw new Error("Invalid project ID");
  }
  const resolved = path.resolve(RESEARCH_ROOT, projectId);
  if (!resolved.startsWith(RESEARCH_ROOT + path.sep)) {
    throw new Error("Invalid project path");
  }
  return resolved;
}

export interface ResearchProjectSummary {
  id: string;
  question: string;
  status: string;
  phase: string;
  created_at: string;
  findings_count: number;
  reports_count: number;
}

export interface ResearchProjectDetail extends ResearchProjectSummary {
  last_report_path?: string;
  feedback_count: number;
}

export async function listResearchProjects(): Promise<ResearchProjectSummary[]> {
  try {
    const entries = await readdir(RESEARCH_ROOT, { withFileTypes: true });
    const projects: ResearchProjectSummary[] = [];
    for (const e of entries) {
      if (!e.isDirectory() || !e.name.startsWith("proj-")) continue;
      const projPath = path.join(RESEARCH_ROOT, e.name);
      try {
        const projectJson = path.join(projPath, "project.json");
        const raw = await readFile(projectJson, "utf8");
        const data = JSON.parse(raw);
        const findingsDir = path.join(projPath, "findings");
        let findingsCount = 0;
        try {
          const files = await readdir(findingsDir);
          findingsCount = files.filter((f) => f.endsWith(".json")).length;
        } catch {
          // ignore
        }
        const reportsDir = path.join(projPath, "reports");
        let reportsCount = 0;
        try {
          const files = await readdir(reportsDir);
          reportsCount = files.filter((f) => f.endsWith(".md")).length;
        } catch {
          // ignore
        }
        projects.push({
          id: data.id || e.name,
          question: data.question || "",
          status: data.status || "unknown",
          phase: data.phase || "explore",
          created_at: data.created_at || "",
          findings_count: findingsCount,
          reports_count: reportsCount,
        });
      } catch {
        // skip broken projects
      }
    }
    projects.sort((a, b) => (b.created_at || "").localeCompare(a.created_at || ""));
    return projects;
  } catch (err) {
    if ((err as NodeJS.ErrnoException).code === "ENOENT") return [];
    throw err;
  }
}

export async function getResearchProject(projectId: string): Promise<ResearchProjectDetail | null> {
  const projPath = safeProjectPath(projectId);
  try {
    const raw = await readFile(path.join(projPath, "project.json"), "utf8");
    const data = JSON.parse(raw);
    let findingsCount = 0;
    try {
      const files = await readdir(path.join(projPath, "findings"));
      findingsCount = files.filter((f) => f.endsWith(".json")).length;
    } catch {
      // ignore
    }
    let reportsCount = 0;
    let lastReportPath: string | undefined;
    try {
      const reportsDir = path.join(projPath, "reports");
      const files = await readdir(reportsDir);
      const mdFiles = files.filter((f) => f.endsWith(".md")).sort().reverse();
      reportsCount = mdFiles.length;
      if (mdFiles.length > 0) lastReportPath = path.join(reportsDir, mdFiles[0]);
    } catch {
      // ignore
    }
    let feedbackCount = 0;
    try {
      const feedbackPath = path.join(projPath, "feedback.jsonl");
      const content = await readFile(feedbackPath, "utf8");
      feedbackCount = content.trim().split("\n").filter(Boolean).length;
    } catch {
      // ignore
    }
    return {
      id: data.id || projectId,
      question: data.question || "",
      status: data.status || "unknown",
      phase: data.phase || "explore",
      created_at: data.created_at || "",
      findings_count: findingsCount,
      reports_count: reportsCount,
      last_report_path: lastReportPath,
      feedback_count: feedbackCount,
    };
  } catch {
    return null;
  }
}

export async function getLatestReportMarkdown(projectId: string): Promise<string | null> {
  const projPath = safeProjectPath(projectId);
  try {
    const reportsDir = path.join(projPath, "reports");
    const files = await readdir(reportsDir);
    const mdFiles = files.filter((f) => f.endsWith(".md")).sort().reverse();
    if (mdFiles.length === 0) return null;
    const content = await readFile(path.join(reportsDir, mdFiles[0]), "utf8");
    return content;
  } catch {
    return null;
  }
}
