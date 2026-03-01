import { readdir, readFile, rm, writeFile } from "fs/promises";
import path from "path";
import { execFileSync, execSync } from "child_process";
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
    const out = execFileSync("python3", ["-c", script], {
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

export interface MemoryAppliedInfo {
  mode?: "v2_applied" | "v2_fallback" | "v2_disabled" | string;
  fallback_reason?: string | null;
  min_confidence?: number;
  confidence_drivers?: {
    strategy_score?: number;
    query_overlap?: number;
    causal_score?: number;
    what_hurt_penalty?: boolean;
    similar_episode_count?: number;
    similar_recency_weight?: number;
  };
  similar_episode_count?: number;
  selected_strategy?: {
    id?: string;
    name?: string;
    domain?: string;
    score?: number;
    confidence?: number;
    selection_confidence?: number;
    policy?: {
      preferred_query_types?: Record<string, number>;
      domain_rank_overrides?: Record<string, number>;
      relevance_threshold?: number;
      critic_threshold?: number;
      revise_rounds?: number;
      required_source_mix?: Record<string, number>;
    };
  };
  expected_benefit?: string;
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
    research_mode?: string;
  };
  phase_history?: string[];
  spend_breakdown?: Record<string, number>;
  prior_knowledge?: PriorKnowledgeInfo;
  memory_applied?: MemoryAppliedInfo;
  /** Set when research_mode is discovery and discovery_analysis.json exists */
  discovery_analysis?: {
    discovery_brief?: {
      novel_connections?: string[];
      emerging_concepts?: string[];
      research_frontier?: string[];
      unexplored_opportunities?: string[];
      key_hypothesis?: string;
    };
  };
  /** Connect phase: thesis (current hypothesis) */
  thesis?: { current?: string; alternatives?: string[]; confidence?: number };
  /** Connect phase: contradictions between sources */
  contradictions?: { contradictions?: Array<{ claim?: string; source_a?: string; source_b?: string; summary?: string }> };
  /** Token Governor: lane used for Verify/Synthesize/Critic (cheap | mid | strong) */
  governor_lane?: string;
  /** Verify: fact_check summary (confirmed / disputed / unverifiable counts) */
  fact_check_summary?: { confirmed: number; disputed: number; unverifiable: number; total: number };
  /** Verify: claim ledger summary for UI */
  claim_ledger_summary?: { total: number; verified: number; authoritative: number; unverified: number; in_contradiction: number };
}

export async function listResearchProjects(): Promise<ResearchProjectSummary[]> {
  try {
    const entries = await readdir(RESEARCH_ROOT, { withFileTypes: true });
    const projectDirs = entries.filter((e) => e.isDirectory() && e.name.startsWith("proj-"));

    const projects = await Promise.all(
      projectDirs.map(async (e): Promise<ResearchProjectSummary | null> => {
        const projPath = path.join(RESEARCH_ROOT, e.name);
        try {
          const [raw, findingsFiles, reportFiles] = await Promise.all([
            readFile(path.join(projPath, "project.json"), "utf8"),
            readdir(path.join(projPath, "findings")).catch(() => [] as string[]),
            readdir(path.join(projPath, "reports")).catch(() => [] as string[]),
          ]);
          const data = JSON.parse(raw) as Record<string, unknown>;
          return {
            id: typeof data.id === "string" ? data.id : e.name,
            question: typeof data.question === "string" ? data.question : "",
            status: typeof data.status === "string" ? data.status : "unknown",
            phase: typeof data.phase === "string" ? data.phase : "explore",
            created_at: typeof data.created_at === "string" ? data.created_at : "",
            findings_count: findingsFiles.filter((f) => f.endsWith(".json")).length,
            reports_count: reportFiles.filter((f) => f.endsWith(".md")).length,
            current_spend: typeof data.current_spend === "number" ? data.current_spend : 0,
            domain: typeof data.domain === "string" ? data.domain : "unknown",
          };
        } catch {
          return null;
        }
      })
    );

    return projects
      .filter((p): p is ResearchProjectSummary => p !== null)
      .sort((a, b) => (b.created_at || "").localeCompare(a.created_at || ""));
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
    let memoryApplied: MemoryAppliedInfo | undefined;
    try {
      const msPath = path.join(projPath, "memory_strategy.json");
      const msRaw = await readFile(msPath, "utf8");
      const ms = JSON.parse(msRaw) as MemoryAppliedInfo;
      if (ms && typeof ms === "object") {
        memoryApplied = ms;
      }
    } catch {
      // ignore
    }
    let discoveryAnalysis: ResearchProjectDetail["discovery_analysis"];
    const config = typeof data.config === "object" && data.config !== null ? (data.config as Record<string, unknown>) : undefined;
    if (config?.research_mode === "discovery") {
      try {
        const daPath = path.join(projPath, "discovery_analysis.json");
        const daRaw = await readFile(daPath, "utf8");
        const da = JSON.parse(daRaw) as { discovery_brief?: { novel_connections?: string[]; emerging_concepts?: string[]; research_frontier?: string[]; unexplored_opportunities?: string[]; key_hypothesis?: string } };
        if (da?.discovery_brief) {
          discoveryAnalysis = { discovery_brief: da.discovery_brief };
        }
      } catch {
        // ignore
      }
    }
    let thesis: ResearchProjectDetail["thesis"];
    try {
      const thesisRaw = await readFile(path.join(projPath, "thesis.json"), "utf8");
      const th = JSON.parse(thesisRaw) as { current?: string; alternatives?: string[]; confidence?: number };
      if (th && typeof th === "object") thesis = th;
    } catch {
      // ignore
    }
    let contradictions: ResearchProjectDetail["contradictions"];
    try {
      const contraRaw = await readFile(path.join(projPath, "contradictions.json"), "utf8");
      const c = JSON.parse(contraRaw) as { contradictions?: Array<{ claim?: string; source_a?: string; source_b?: string; summary?: string }> };
      if (c && typeof c === "object") contradictions = c;
    } catch {
      // ignore
    }
    let governorLane: string | undefined;
    try {
      const glRaw = await readFile(path.join(projPath, "governor_lane.json"), "utf8");
      const s = JSON.parse(glRaw);
      if (typeof s === "string") governorLane = s;
    } catch {
      // ignore
    }
    let factCheckSummary: ResearchProjectDetail["fact_check_summary"];
    try {
      const fcRaw = await readFile(path.join(projPath, "verify", "fact_check.json"), "utf8");
      const fc = JSON.parse(fcRaw) as { facts?: Array<{ verification_status?: string }> };
      const facts = fc?.facts ?? [];
      let confirmed = 0, disputed = 0, unverifiable = 0;
      for (const f of facts) {
        const s = (f.verification_status ?? "").toLowerCase();
        if (s === "confirmed" || s === "supported") confirmed++;
        else if (s === "disputed") disputed++;
        else unverifiable++;
      }
      factCheckSummary = { confirmed, disputed, unverifiable, total: facts.length };
    } catch {
      // ignore
    }
    let claimLedgerSummary: ResearchProjectDetail["claim_ledger_summary"];
    try {
      const clRaw = await readFile(path.join(projPath, "verify", "claim_ledger.json"), "utf8");
      const cl = JSON.parse(clRaw) as { claims?: Array<{ is_verified?: boolean; verification_tier?: string; in_contradiction?: boolean }> };
      const claims = cl?.claims ?? [];
      let verified = 0, authoritative = 0, unverified = 0, inContradiction = 0;
      for (const c of claims) {
        const tier = (c.verification_tier ?? "").toUpperCase();
        if (tier === "VERIFIED" || (c.is_verified && tier !== "UNVERIFIED")) verified++;
        else if (tier === "AUTHORITATIVE") authoritative++;
        else unverified++;
        if (c.in_contradiction) inContradiction++;
      }
      claimLedgerSummary = {
        total: claims.length,
        verified,
        authoritative,
        unverified,
        in_contradiction: inContradiction,
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
      memory_applied: memoryApplied,
      discovery_analysis: discoveryAnalysis,
      thesis,
      contradictions,
      governor_lane: governorLane,
      fact_check_summary: factCheckSummary,
      claim_ledger_summary: claimLedgerSummary,
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

/** Approve or reject a project in pending_review. Approve: set status=active, phase=synthesize and sync progress.json so UI shows correct phase. */
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

  if (action === "approve") {
    const progressPath = path.join(projPath, "progress.json");
    const now = new Date().toISOString().replace(/\.\d{3}Z$/, "Z");
    try {
      const progressRaw = await readFile(progressPath, "utf8");
      const progress = JSON.parse(progressRaw) as Record<string, unknown>;
      progress.phase = "synthesize";
      progress.step = "Starting synthesize phase...";
      progress.step_started_at = now;
      progress.heartbeat = now;
      progress.step_index = 0;
      progress.step_total = 0;
      progress.alive = false;
      await writeFile(progressPath, JSON.stringify(progress, null, 2), "utf8");
    } catch {
      await writeFile(
        progressPath,
        JSON.stringify(
          {
            phase: "synthesize",
            step: "Starting synthesize phase...",
            step_started_at: now,
            heartbeat: now,
            step_index: 0,
            step_total: 0,
            steps_completed: [],
            active_steps: [],
            started_at: now,
            alive: false,
          },
          null,
          2
        ),
        "utf8"
      );
    }
  }

  return {
    status: data.status as string,
    phase: data.phase as string | undefined,
  };
}

/** Cancel a running research project: kill processes, set status=cancelled, mark related RUNNING jobs as FAILED. */
export async function cancelResearchProject(projectId: string): Promise<{ killed: number; jobsReconciled: number; status: string }> {
  const projPath = safeProjectPath(projectId);
  const projectJsonPath = path.join(projPath, "project.json");
  const jobsRoot = path.join(OPERATOR_ROOT, "jobs");
  let killed = 0;
  let jobsReconciled = 0;

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
    const dayDirs = await readdir(jobsRoot, { withFileTypes: true });
    for (const day of dayDirs.filter((d) => d.isDirectory()).map((d) => d.name)) {
      const dayPath = path.join(jobsRoot, day);
      const entries = await readdir(dayPath, { withFileTypes: true });
      for (const ent of entries) {
        if (!ent.isDirectory()) continue;
        const jobPath = path.join(dayPath, ent.name, "job.json");
        try {
          const raw = await readFile(jobPath, "utf8");
          const job = JSON.parse(raw) as Record<string, unknown>;
          if (job.status === "RUNNING" && job.request === projectId) {
            job.status = "FAILED";
            job.finished_at = new Date().toISOString();
            job.error = "Project cancelled by user";
            job.exit_code = -9;
            await writeFile(jobPath, JSON.stringify(job, null, 2), "utf8");
            jobsReconciled += 1;
          }
        } catch {
          // skip invalid/missing
        }
      }
    }
  } catch {
    // jobs dir missing or unreadable
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
  return { killed, jobsReconciled, status: "cancelled" };
}

/** Manifest entry from reports/manifest.json (post-process / pipeline). */
interface ReportManifestEntry {
  filename: string;
  generated_at?: string;
  is_revised?: boolean;
  quality_score?: number;
  path?: string;
  is_final?: boolean;
}

export async function getLatestReportMarkdown(projectId: string): Promise<string | null> {
  const projPath = safeProjectPath(projectId);
  const reportsDir = path.join(projPath, "reports");
  try {
    const manifestPath = path.join(reportsDir, "manifest.json");
    let chosenFile: string | null = null;
    try {
      const manifestRaw = await readFile(manifestPath, "utf8");
      const manifest = JSON.parse(manifestRaw) as { reports?: ReportManifestEntry[] };
      const reports = manifest.reports ?? [];
      const finalEntry = reports.find((r) => r.is_final);
      const entry = finalEntry ?? reports[reports.length - 1];
      if (entry?.filename) chosenFile = entry.filename;
    } catch {
      // no manifest or invalid — fallback to dir listing
    }
    if (!chosenFile) {
      const files = await readdir(reportsDir);
      const mdFiles = files.filter((f) => f.endsWith(".md")).sort().reverse();
      if (mdFiles.length === 0) return null;
      chosenFile = mdFiles[0];
    }
    const content = await readFile(path.join(reportsDir, chosenFile), "utf8");
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
  const reliabilityByUrl: Record<string, number> = {};
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
  verification_tier?: "VERIFIED" | "AUTHORITATIVE" | "UNVERIFIED";
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
    const claims: AuditClaim[] = (data.claims ?? []).map((raw) => {
      const c = raw as Record<string, unknown>;
      const tier = c.verification_tier as string | undefined;
      const verification_tier: AuditClaim["verification_tier"] =
        tier === "VERIFIED" || tier === "AUTHORITATIVE" || tier === "UNVERIFIED" ? tier : undefined;
      return {
        claim_id: String(c.claim_id ?? ""),
        text: String(c.text ?? "").slice(0, 500),
        is_verified: Boolean(c.is_verified),
        verification_tier,
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

export interface CritiqueData {
  score: number;
  weaknesses: string[];
  suggestions: string[];
  strengths?: string[];
  pass?: boolean;
}

/** Read critic assessment from research/{projectId}/verify/critique.json. Returns null if file missing. */
export async function getCritique(projectId: string): Promise<CritiqueData | null> {
  const projPath = safeProjectPath(projectId);
  const critiquePath = path.join(projPath, "verify", "critique.json");
  try {
    const raw = await readFile(critiquePath, "utf8");
    const data = JSON.parse(raw) as Record<string, unknown>;
    const score = typeof data.score === "number" ? data.score : 0;
    const weaknesses = Array.isArray(data.weaknesses) ? (data.weaknesses as string[]) : [];
    const suggestions = Array.isArray(data.suggestions) ? (data.suggestions as string[]) : [];
    const strengths = Array.isArray(data.strengths) ? (data.strengths as string[]) : undefined;
    const pass = typeof data.pass === "boolean" ? data.pass : undefined;
    return { score, weaknesses, suggestions, strengths, pass };
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
