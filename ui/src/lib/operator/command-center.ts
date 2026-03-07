import { execFile } from "child_process";
import { readdir, readFile } from "fs/promises";
import path from "path";
import { promisify } from "util";

const exec = promisify(execFile);
const AGENT_ROOT = process.env.AGENT_ROOT ?? "/root/agent/workspace";
const MISSIONS_ROOT = path.join(AGENT_ROOT, "logs", "missions");
const PORTFOLIO_ROOT = path.join(AGENT_ROOT, "logs", "portfolios");
const CAMPAIGN_ROOT = path.join(AGENT_ROOT, "logs", "campaigns");
const JUNE_COMMAND_RUN = path.join(AGENT_ROOT, "bin", "june-command-run");

type Json = Record<string, unknown>;

export interface CommandMissionTask {
  task_id: string;
  kind: string;
  description: string;
  status: string;
  depends_on: string[];
  metadata: Record<string, unknown>;
}

export interface CommandDecisionSummary {
  overall?: string;
  next_action?: string;
  mission_status?: string;
  rationale?: string;
  decided_at?: string;
  attempt_id?: string;
  substance_stage?: string;
  question_status?: string;
  evidence_delta?: string;
  countercheck_status?: string;
  why_not_done?: string;
  next_best_test?: string;
}

export interface CommandEnvelopeSummary {
  run_dir?: string;
  summary_file?: string;
  overall?: string;
  recommendation?: string;
  atlas_overall?: string;
  atlas_recommendation?: string;
  attempt_id?: string;
}

export interface CommandMissionSummary {
  id: string;
  objective: string;
  plan: string;
  intent: string;
  status: string;
  lifecycle: "active" | "awaiting_next_test" | "done" | "paused" | "blocked" | "planned" | "unknown";
  portfolio_id?: string;
  campaign_id?: string;
  updated_at?: string;
  created_at?: string;
  request_text?: string;
  runtime_budget_sec?: number;
  decision?: CommandDecisionSummary;
  envelope?: CommandEnvelopeSummary;
  tasks: CommandMissionTask[];
}

export interface PortfolioSummary {
  id: string;
  class: string;
  owner: string;
  campaigns: number;
  strategy?: {
    active_count?: number;
    hold_count?: number;
    stop_count?: number;
    top_priority_campaigns?: string[];
    last_reviewed_mission?: string;
  };
}

export interface CampaignSummary {
  id: string;
  plan: string;
  objective: string;
  latest?: {
    overall?: string;
    next_action?: string;
  };
  strategy?: {
    avg_score?: number;
    review_count?: number;
    latest_failure_genome?: string;
    latest_question_status?: string;
    recommended_disposition?: string;
  };
}

export interface CommandCenterData {
  missions: CommandMissionSummary[];
  portfolios: PortfolioSummary[];
  campaigns: CampaignSummary[];
  stats: {
    totalMissions: number;
    activeMissions: number;
    passCampaigns: number;
    portfolios: number;
    pushCampaigns: number;
    holdCampaigns: number;
    stopCampaigns: number;
  };
}

export interface CommandCenterActionInput {
  action: "create" | "show" | "pause" | "resume" | "retry" | "replan";
  missionId?: string;
  objective?: string;
  requestText?: string;
  reason?: string;
  execute?: boolean;
}

export interface CommandCenterActionResult {
  ok: boolean;
  mission?: CommandMissionSummary;
  data?: CommandCenterData;
  command?: string[];
  rawOutput?: string;
  error?: string;
}

export async function listCommandCenter(): Promise<CommandCenterData> {
  const [missions, portfolios, campaigns] = await Promise.all([
    listMissions(),
    listPortfolios(),
    listCampaigns(),
  ]);

  return {
    missions,
    portfolios,
    campaigns,
    stats: {
      totalMissions: missions.length,
      activeMissions: missions.filter((mission) => mission.status === "running" || mission.status === "planned").length,
      passCampaigns: campaigns.filter((campaign) => campaign.latest?.overall === "PASS").length,
      portfolios: portfolios.length,
      pushCampaigns: campaigns.filter((campaign) => campaign.strategy?.recommended_disposition === "push").length,
      holdCampaigns: campaigns.filter((campaign) => campaign.strategy?.recommended_disposition === "hold").length,
      stopCampaigns: campaigns.filter((campaign) => campaign.strategy?.recommended_disposition === "stop").length,
    },
  };
}

export async function executeCommandCenterAction(input: CommandCenterActionInput): Promise<CommandCenterActionResult> {
  if (input.action === "show") {
    if (!input.missionId) {
      return { ok: false, error: "missionId is required for show" };
    }
    const mission = await readMission(input.missionId);
    return {
      ok: true,
      mission,
      data: await listCommandCenter(),
      command: [JUNE_COMMAND_RUN, "--mission-id", input.missionId, "--show"],
    };
  }

  const args = buildArgs(input);
  try {
    const { stdout, stderr } = await exec(JUNE_COMMAND_RUN, args, {
      timeout: 30_000,
      env: { ...process.env },
    });
    const rawOutput = [stdout, stderr].filter(Boolean).join("\n").trim();
    const missionId = input.missionId ?? parseMissionId(rawOutput);
    const mission = missionId ? await readMission(missionId) : undefined;
    return {
      ok: true,
      mission,
      data: await listCommandCenter(),
      command: [JUNE_COMMAND_RUN, ...args],
      rawOutput,
    };
  } catch (error) {
    const err = error as NodeJS.ErrnoException & { stdout?: string; stderr?: string };
    const rawOutput = [err.stdout, err.stderr].filter(Boolean).join("\n").trim();
    return {
      ok: false,
      error: rawOutput || err.message,
      command: [JUNE_COMMAND_RUN, ...args],
      rawOutput,
    };
  }
}

async function listMissions(): Promise<CommandMissionSummary[]> {
  const dirs = await readdir(MISSIONS_ROOT, { withFileTypes: true }).catch(() => []);
  const items = await Promise.all(
    dirs
      .filter((entry) => entry.isDirectory())
      .map(async (entry) => readMission(entry.name).catch(() => null)),
  );

  return items
    .filter((item): item is CommandMissionSummary => item !== null)
    .sort((left, right) => String(right.updated_at ?? "").localeCompare(String(left.updated_at ?? "")));
}

async function readMission(missionId: string): Promise<CommandMissionSummary> {
  const missionDir = path.join(MISSIONS_ROOT, missionId);
  const [missionRaw, graphRaw, decisionRaw, envelopeRaw] = await Promise.all([
    readJson(path.join(missionDir, "mission.json")),
    readJson(path.join(missionDir, "task_graph.json")),
    readJson(path.join(missionDir, "decision.json"), true),
    readJson(path.join(missionDir, "result_envelope.json"), true),
  ]);

  const missionData = missionRaw as Json;
  const graphData = graphRaw as { nodes?: CommandMissionTask[] };
  const decision = (decisionRaw ?? {}) as CommandDecisionSummary;
  const envelope = (envelopeRaw ?? {}) as CommandEnvelopeSummary;
  const tasks = Array.isArray(graphData.nodes) ? graphData.nodes : [];
  const metadata = asObject(missionData.metadata);

  return {
    id: String(missionData.mission_id ?? missionId),
    objective: String(missionData.objective ?? ""),
    plan: String(missionData.plan ?? "unknown"),
    intent: String(missionData.intent ?? "unknown"),
    status: String(missionData.status ?? decision.mission_status ?? "unknown"),
    lifecycle: classifyLifecycle(
      String(missionData.status ?? decision.mission_status ?? "unknown"),
      envelope.overall,
      decision.next_action,
    ),
    portfolio_id: asOptionalString(metadata.portfolio_id),
    campaign_id: asOptionalString(metadata.campaign_id),
    updated_at:
      asOptionalString(metadata.replanned_at) ??
      asOptionalString(metadata.resumed_at) ??
      asOptionalString(metadata.retry_requested_at) ??
      asOptionalString(metadata.paused_at) ??
      decision.decided_at ??
      String(missionData.created_at ?? ""),
    created_at: asOptionalString(missionData.created_at),
    request_text: asOptionalString(missionData.request_text),
    runtime_budget_sec: asOptionalNumber(asObject(missionData.resource_profile).runtime_budget_sec),
    decision,
    envelope,
    tasks,
  };
}

async function listPortfolios(): Promise<PortfolioSummary[]> {
  const files = await readdir(PORTFOLIO_ROOT).catch(() => []);
  const items = await Promise.all(
    files
      .filter((name) => name.endsWith(".json"))
      .map(async (name) => {
        const data = (await readJson(path.join(PORTFOLIO_ROOT, name))) as any;
        return {
          id: data.portfolio.id,
          class: data.portfolio.class,
          owner: data.portfolio.owner,
          campaigns: Object.keys(data.campaigns ?? {}).length,
          strategy: data.strategy_summary,
        } satisfies PortfolioSummary;
      }),
  );
  return items.sort((left, right) => left.id.localeCompare(right.id));
}

async function listCampaigns(): Promise<CampaignSummary[]> {
  const files = await readdir(CAMPAIGN_ROOT).catch(() => []);
  const items = await Promise.all(
    files
      .filter((name) => name.endsWith(".json"))
      .map(async (name) => {
        const data = (await readJson(path.join(CAMPAIGN_ROOT, name))) as any;
        return {
          id: data.campaign.id,
          plan: data.campaign.plan,
          objective: data.campaign.objective,
          latest: data.latest,
          strategy: data.strategy,
        } satisfies CampaignSummary;
      }),
  );
  return items.sort((left, right) => left.id.localeCompare(right.id));
}

async function readJson(file: string, optional = false): Promise<Json | null> {
  try {
    const raw = await readFile(file, "utf8");
    return JSON.parse(raw) as Json;
  } catch (error) {
    if (optional) return null;
    throw error;
  }
}

function buildArgs(input: CommandCenterActionInput): string[] {
  switch (input.action) {
    case "create": {
      if (!input.objective?.trim()) {
        throw new Error("objective is required");
      }
      const args = [input.objective.trim()];
      if (input.requestText?.trim()) {
        args.push("--request-text", input.requestText.trim());
      }
      if (input.execute !== false) {
        args.push("--execute");
      }
      return args;
    }
    case "pause":
    case "resume":
    case "retry": {
      if (!input.missionId) {
        throw new Error("missionId is required");
      }
      const args = ["--mission-id", input.missionId, `--${input.action}`];
      if (input.reason?.trim()) {
        args.push("--reason", input.reason.trim());
      }
      return args;
    }
    case "replan": {
      if (!input.missionId) {
        throw new Error("missionId is required");
      }
      const args = ["--mission-id", input.missionId, "--replan"];
      if (input.objective?.trim()) {
        args.push(input.objective.trim());
      }
      if (input.requestText?.trim()) {
        args.push("--request-text", input.requestText.trim());
      }
      if (input.reason?.trim()) {
        args.push("--reason", input.reason.trim());
      }
      return args;
    }
    case "show":
      throw new Error("show is handled without shell execution");
  }
}

function parseMissionId(output: string): string | undefined {
  const match = output.match(/^MISSION_ID=(.+)$/m);
  return match?.[1]?.trim();
}

function asObject(value: unknown): Record<string, unknown> {
  return value && typeof value === "object" ? (value as Record<string, unknown>) : {};
}

function asOptionalString(value: unknown): string | undefined {
  return typeof value === "string" && value.length > 0 ? value : undefined;
}

function asOptionalNumber(value: unknown): number | undefined {
  return typeof value === "number" ? value : undefined;
}

function classifyLifecycle(
  status: string,
  overall?: string,
  nextAction?: string,
): CommandMissionSummary["lifecycle"] {
  const normalized = status.toLowerCase();
  if (normalized === "paused") return "paused";
  if (normalized === "done") return "done";
  if (normalized === "blocked" || normalized === "failed") return "blocked";
  if (normalized === "planned") return "planned";
  if (normalized === "running" && overall === "PASS" && nextAction === "new_test") {
    return "awaiting_next_test";
  }
  if (normalized === "running") return "active";
  return "unknown";
}
