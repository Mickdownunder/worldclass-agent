import { execFile } from "child_process";
import { promisify } from "util";
import path from "path";
import { OPERATOR_ROOT } from "./config";

const exec = promisify(execFile);
const BRAIN_BIN = path.join(OPERATOR_ROOT, "bin", "brain");

async function brainJson(args: string[]): Promise<unknown> {
  const { stdout } = await exec(BRAIN_BIN, args, {
    timeout: 15000,
    env: { ...process.env },
  });
  return JSON.parse(stdout) as unknown;
}

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

export interface Principle {
  id?: string;
  principle_type?: string;
  description?: string;
  domain?: string;
  metric_score?: number;
  usage_count?: number;
  success_count?: number;
  evidence_json?: string;
  created_at?: string;
}

export async function getPrinciples(limit = 50, domain?: string): Promise<Principle[]> {
  try {
    const args = ["principles", "--limit", String(limit)];
    if (domain) args.push("--domain", domain);
    const data = await brainJson(args) as { principles?: Principle[] };
    return data.principles ?? [];
  } catch {
    return [];
  }
}

export interface SourceCredibilityRow {
  domain: string;
  times_used?: number;
  verified_count?: number;
  failed_verification_count?: number;
  learned_credibility?: number;
  last_updated?: string;
}

export async function getSourceCredibility(limit = 50): Promise<SourceCredibilityRow[]> {
  try {
    const data = await brainJson(["credibility", "--limit", String(limit)]) as { credibility?: SourceCredibilityRow[] };
    return data.credibility ?? [];
  } catch {
    return [];
  }
}

export interface ProjectOutcomeRow {
  project_id?: string;
  domain?: string;
  critic_score?: number;
  user_verdict?: string;
  completed_at?: string;
}

export async function getProjectOutcomes(limit = 100): Promise<{ outcomes: ProjectOutcomeRow[]; total: number }> {
  try {
    const data = await brainJson(["outcomes", "--limit", String(limit)]) as { outcomes?: ProjectOutcomeRow[]; total?: number };
    return { outcomes: data.outcomes ?? [], total: data.total ?? 0 };
  } catch {
    return { outcomes: [], total: 0 };
  }
}

export interface BrainDecision {
  id?: string;
  phase?: string;
  reasoning?: string;
  decision?: string;
  confidence?: number;
  trace_id?: string;
  ts?: string;
  inputs?: string;
}

export async function getDecisions(limit = 30): Promise<BrainDecision[]> {
  try {
    const data = await brainJson(["decisions", "--limit", String(limit)]) as { decisions?: BrainDecision[] };
    return data.decisions ?? [];
  } catch {
    return [];
  }
}

export interface EntityRow {
  id?: string;
  name?: string;
  type?: string;
  first_seen_project?: string;
  properties_json?: string;
  created_at?: string;
}

export interface EntityRelation {
  id?: string;
  entity_a_id?: string;
  entity_b_id?: string;
  relation_type?: string;
  name_a?: string;
  name_b?: string;
}

export async function getEntities(options?: { type?: string; project?: string; limit?: number }): Promise<{ entities: EntityRow[]; relations: EntityRelation[] }> {
  try {
    const args = ["entities"];
    if (options?.type) args.push("--type", options.type);
    if (options?.project) args.push("--project", options.project);
    const data = await brainJson(args) as { entities?: EntityRow[]; relations?: EntityRelation[] };
    return { entities: data.entities ?? [], relations: data.relations ?? [] };
  } catch {
    return { entities: [], relations: [] };
  }
}
