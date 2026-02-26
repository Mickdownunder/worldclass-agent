import { readdir, readFile, rm, writeFile } from "fs/promises";
import path from "path";
import { execSync } from "child_process";
import { OPERATOR_ROOT } from "./config";

export interface CalibratedThresholds {
  findings_count_min?: number;
  unique_source_count_min?: number;
  verified_claim_count_min?: number;
  claim_support_rate_min?: number;
  high_reliability_source_ratio_min?: number;
}

/** Fetch current calibrated evidence-gate thresholds (from project_outcomes). Returns null if < 10 successful projects. */
export async function getCalibratedThresholds(): Promise<CalibratedThresholds | null> {
  try {
    const script = [
      "import json, os, sys",
      "root = os.environ.get('OPERATOR_ROOT', '/root/operator')",
      "sys.path.insert(0, root)",
      "try:",
      "  from tools.research_calibrator import get_calibrated_thresholds",
      "  t = get_calibrated_thresholds()",
      "  print(json.dumps(t if t is not None else {}))",
      "except Exception:",
      "  print('{}')",
    ].join("\n");
    const out = execSync("python3 -c " + JSON.stringify(script), {
      cwd: OPERATOR_ROOT,
      encoding: "utf8",
      timeout: 10000,
      env: { ...process.env, OPERATOR_ROOT },
    }).trim();
    const t = JSON.parse(out || "{}") as CalibratedThresholds;
    if (Object.keys(t).length === 0) return null;
    return t;
  } catch {
    return null;
  }
}

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
  current_spend: number;
  domain: string;
}

export interface QualityGateMetrics {
  findings_count: number;
  unique_source_count: number;
  verified_claim_count: number;
  claim_support_rate: number;
  high_reliability_source_ratio: number;
  read_attempts: number;
  read_successes: number;
  read_failures: number;
}

export interface EvidenceGate {
  status: string;
  fail_code?: string;
  metrics: QualityGateMetrics;
  reasons: string[];
}

export interface PhaseTiming {
  started_at: string;
  completed_at: string;
  duration_s: number;
}

export interface PriorKnowledgeInfo {
  principles_count: number;
  findings_count: number;
}

export interface ResearchProjectDetail extends ResearchProjectSummary {
  completed_at?: string;
  last_report_path?: string;
  feedback_count: number;
  quality_gate?: {
    evidence_gate?: EvidenceGate;
    critic_score?: number;
    quality_gate_status?: string;
    calibrated_thresholds?: {
      findings_count_min?: number;
      unique_source_count_min?: number;
      verified_claim_count_min?: number;
    };
  };
  phase_timings?: Record<string, PhaseTiming>;
  config?: {
    budget_limit?: number;
    max_sources?: number;
  };
  phase_history?: string[];
  spend_breakdown?: Record<string, number>;
  prior_knowledge?: PriorKnowledgeInfo;
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
        const data = JSON.parse(raw) as Record<string, unknown>;
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
          id: typeof data.id === "string" ? data.id : e.name,
          question: typeof data.question === "string" ? data.question : "",
          status: typeof data.status === "string" ? data.status : "unknown",
          phase: typeof data.phase === "string" ? data.phase : "explore",
          created_at: typeof data.created_at === "string" ? data.created_at : "",
          findings_count: findingsCount,
          reports_count: reportsCount,
          current_spend: typeof data.current_spend === "number" ? data.current_spend : 0,
          domain: typeof data.domain === "string" ? data.domain : "unknown",
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
    const data = JSON.parse(raw) as Record<string, unknown>;
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
    let priorKnowledge: PriorKnowledgeInfo | undefined;
    try {
      const pkPath = path.join(projPath, "prior_knowledge.json");
      const pkRaw = await readFile(pkPath, "utf8");
      const pk = JSON.parse(pkRaw) as { principles?: unknown[]; findings?: unknown[] };
      priorKnowledge = {
        principles_count: Array.isArray(pk.principles) ? pk.principles.length : 0,
        findings_count: Array.isArray(pk.findings) ? pk.findings.length : 0,
      };
    } catch {
      // ignore
    }
    return {
      id: typeof data.id === "string" ? data.id : projectId,
      question: typeof data.question === "string" ? data.question : "",
      status: typeof data.status === "string" ? data.status : "unknown",
      phase: typeof data.phase === "string" ? data.phase : "explore",
      created_at: typeof data.created_at === "string" ? data.created_at : "",
      completed_at: typeof data.completed_at === "string" ? data.completed_at : undefined,
      findings_count: findingsCount,
      reports_count: reportsCount,
      current_spend: typeof data.current_spend === "number" ? data.current_spend : 0,
      domain: typeof data.domain === "string" ? data.domain : "unknown",
      last_report_path: lastReportPath,
      feedback_count: feedbackCount,
      quality_gate:
        typeof data.quality_gate === "object" && data.quality_gate !== null
          ? (data.quality_gate as ResearchProjectDetail["quality_gate"])
          : undefined,
      phase_timings:
        typeof data.phase_timings === "object" && data.phase_timings !== null
          ? (data.phase_timings as Record<string, PhaseTiming>)
          : undefined,
      config:
        typeof data.config === "object" && data.config !== null
          ? (data.config as ResearchProjectDetail["config"])
          : undefined,
      phase_history: Array.isArray(data.phase_history)
        ? data.phase_history.filter((p): p is string => typeof p === "string")
        : undefined,
      spend_breakdown:
        typeof data.spend_breakdown === "object" && data.spend_breakdown !== null
          ? (data.spend_breakdown as Record<string, number>)
          : undefined,
      prior_knowledge: priorKnowledge,
    };
  } catch {
    return null;
  }
}

/** Permanently delete a research project (removes project folder and all contents). Kills any running processes for this project first. */
export async function deleteResearchProject(projectId: string): Promise<void> {
  await cancelResearchProject(projectId).catch(() => {});
  const projPath = safeProjectPath(projectId);
  await rm(projPath, { recursive: true, force: true });
}

/** Approve or reject a project in pending_review. Approve: set status=active, phase=synthesize. Reject: set status=failed_rejected_by_reviewer. */
export async function approveProject(
  projectId: string,
  action: "approve" | "reject"
): Promise<{ status: string; phase?: string }> {
  const projPath = safeProjectPath(projectId);
  const projectJsonPath = path.join(projPath, "project.json");
  const raw = await readFile(projectJsonPath, "utf8");
  const data = JSON.parse(raw) as Record<string, unknown>;
  if (action === "approve") {
    data.status = "active";
    data.phase = "synthesize";
  } else {
    data.status = "failed_rejected_by_reviewer";
  }
  await writeFile(projectJsonPath, JSON.stringify(data, null, 2), "utf8");
  return {
    status: data.status as string,
    phase: data.phase as string | undefined,
  };
}

/** Cancel a running research project: find and kill matching processes, set status=cancelled. */
export async function cancelResearchProject(projectId: string): Promise<{ killed: number; status: string }> {
  const projPath = safeProjectPath(projectId);
  const projectJsonPath = path.join(projPath, "project.json");
  let killed = 0;
  try {
    const pidsOut = execSync(
      `ps aux | grep -E '${projectId}|${path.basename(projPath)}' | grep -v grep | awk '{print $2}'`,
      { encoding: "utf8", maxBuffer: 1024 * 1024 }
    );
    const pids = pidsOut.trim().split(/\s+/).filter(Boolean);
    for (const pid of pids) {
      try {
        execSync(`kill ${pid}`, { timeout: 2000 });
        killed += 1;
      } catch {
        // process may already be gone
      }
    }
  } catch {
    // no matching processes
  }
  try {
    const raw = await readFile(projectJsonPath, "utf8");
    const data = JSON.parse(raw) as Record<string, unknown>;
    data.status = "cancelled";
    data.cancelled_at = new Date().toISOString();
    data.completed_at = new Date().toISOString();
    await writeFile(projectJsonPath, JSON.stringify(data, null, 2), "utf8");
  } catch {
    // project may not exist if already deleted
  }
  return { killed, status: "cancelled" };
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

/**
 * Returns the latest PDF report path and filename for a project, or null if none exists.
 */
export async function getLatestReportPdf(
  projectId: string
): Promise<{ path: string; filename: string } | null> {
  const projPath = safeProjectPath(projectId);
  try {
    const reportsDir = path.join(projPath, "reports");
    const files = await readdir(reportsDir);
    const pdfFiles = files.filter((f) => f.endsWith(".pdf")).sort().reverse();
    if (pdfFiles.length === 0) return null;
    const filename = pdfFiles[0];
    return {
      path: path.join(reportsDir, filename),
      filename,
    };
  } catch {
    return null;
  }
}

export interface Finding {
  id: string;
  url?: string;
  title?: string;
  excerpt?: string;
  source?: string;
  confidence?: number;
}

export async function getFindings(projectId: string): Promise<Finding[]> {
  const projPath = safeProjectPath(projectId);
  const findingsDir = path.join(projPath, "findings");
  try {
    const files = await readdir(findingsDir);
    const jsonFiles = files.filter((f) => f.endsWith(".json") && !f.includes("_content"));
    const findings: Finding[] = [];
    for (const f of jsonFiles.sort()) {
      try {
        const raw = await readFile(path.join(findingsDir, f), "utf8");
        const data = JSON.parse(raw) as Record<string, unknown>;
        findings.push({
          id: f.replace(".json", ""),
          url: typeof data.url === "string" ? data.url : undefined,
          title: typeof data.title === "string" ? data.title : undefined,
          excerpt: typeof data.excerpt === "string" ? data.excerpt : undefined,
          source: typeof data.source === "string" ? data.source : undefined,
          confidence: typeof data.confidence === "number" ? data.confidence : undefined,
        });
      } catch {
        findings.push({ id: f.replace(".json", "") });
      }
    }
    return findings;
  } catch {
    return [];
  }
}

export interface Source {
  id: string;
  url?: string;
  type?: string;
  /** Initial confidence/source_quality (pre-verify); 0.5 = unknown. */
  confidence?: number;
  /** Verified reliability from verify/source_reliability.json; set only after verify phase. */
  reliability_score?: number;
  /** "initial" = pre-verify (confidence only); "verified" = has reliability_score from verify. */
  score_source?: "initial" | "verified";
}

export async function getSources(projectId: string): Promise<Source[]> {
  const projPath = safeProjectPath(projectId);
  const sourcesDir = path.join(projPath, "sources");
  let reliabilityByUrl: Record<string, number> = {};
  try {
    const verifyPath = path.join(projPath, "verify", "source_reliability.json");
    const raw = await readFile(verifyPath, "utf8");
    const data = JSON.parse(raw) as { sources?: Array<{ url?: string; reliability_score?: number }> };
    for (const s of data.sources ?? []) {
      if (typeof s.url === "string" && typeof s.reliability_score === "number") {
        reliabilityByUrl[s.url] = s.reliability_score;
      }
    }
  } catch {
    // no verify data yet
  }
  try {
    const files = await readdir(sourcesDir);
    const jsonFiles = files.filter((f) => f.endsWith(".json") && !f.includes("_content"));
    const sources: Source[] = [];
    for (const f of jsonFiles.sort()) {
      try {
        const raw = await readFile(path.join(sourcesDir, f), "utf8");
        const data = JSON.parse(raw) as Record<string, unknown>;
        const url = typeof data.url === "string" ? data.url : undefined;
        const reliability_score = url ? reliabilityByUrl[url] : undefined;
        sources.push({
          id: f.replace(".json", ""),
          url,
          type: typeof data.source_quality === "string" ? data.source_quality : undefined,
          confidence: typeof data.confidence === "number" ? data.confidence : undefined,
          reliability_score: typeof reliability_score === "number" ? reliability_score : undefined,
          score_source: typeof reliability_score === "number" ? "verified" : "initial",
        });
      } catch {
        sources.push({ id: f.replace(".json", "") });
      }
    }
    return sources;
  } catch {
    return [];
  }
}

export interface ReportEntry {
  filename: string;
  content: string;
}

export async function getAllReports(projectId: string): Promise<ReportEntry[]> {
  const projPath = safeProjectPath(projectId);
  const reportsDir = path.join(projPath, "reports");
  try {
    const files = await readdir(reportsDir);
    const mdFiles = files.filter((f) => f.endsWith(".md")).sort().reverse();
    const reports: ReportEntry[] = [];
    for (const f of mdFiles) {
      try {
        const content = await readFile(path.join(reportsDir, f), "utf8");
        reports.push({ filename: f, content });
      } catch {
        reports.push({ filename: f, content: "" });
      }
    }
    return reports;
  } catch {
    return [];
  }
}

export interface AuditClaim {
  claim_id: string;
  text: string;
  is_verified: boolean;
  verification_reason?: string;
  supporting_source_ids: string[];
}

export interface AuditData {
  claims: AuditClaim[];
  source?: "claim_evidence_map_latest" | "claim_ledger";
}

export async function getAudit(projectId: string): Promise<AuditData | null> {
  const projPath = safeProjectPath(projectId);
  const verifyDir = path.join(projPath, "verify");
  try {
    const evidencePath = path.join(verifyDir, "claim_evidence_map_latest.json");
    const ledgerPath = path.join(verifyDir, "claim_ledger.json");
    let raw: string;
    let source: "claim_evidence_map_latest" | "claim_ledger";
    try {
      raw = await readFile(evidencePath, "utf8");
      source = "claim_evidence_map_latest";
    } catch {
      raw = await readFile(ledgerPath, "utf8");
      source = "claim_ledger";
    }
    const data = JSON.parse(raw) as { claims?: unknown[] };
    const claims = (data.claims ?? []).map((raw) => {
      const c = raw as Record<string, unknown>;
      return {
        claim_id: String(c.claim_id ?? ""),
        text: String(c.text ?? "").slice(0, 500),
        is_verified: Boolean(c.is_verified),
        verification_reason: c.verification_reason != null ? String(c.verification_reason) : undefined,
        supporting_source_ids: Array.isArray(c.supporting_source_ids)
          ? (c.supporting_source_ids as string[])
          : [],
      };
    });
    return { claims, source };
  } catch {
    return null;
  }
}

export async function getAuditLog(
  projectId: string
): Promise<Array<{ ts: string; event: string; detail?: Record<string, unknown> }>> {
  const projPath = safeProjectPath(projectId);
  try {
    const content = await readFile(path.join(projPath, "audit_log.jsonl"), "utf8");
    return content
      .trim()
      .split("\n")
      .filter(Boolean)
      .map((line) => {
        try {
          return JSON.parse(line) as {
            ts: string;
            event: string;
            detail?: Record<string, unknown>;
          };
        } catch {
          return null;
        }
      })
      .filter((entry): entry is { ts: string; event: string; detail?: Record<string, unknown> } => {
        return (
          entry !== null &&
          typeof entry.ts === "string" &&
          typeof entry.event === "string"
        );
      });
  } catch {
    return [];
  }
}
