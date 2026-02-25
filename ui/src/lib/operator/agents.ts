import { readFile, readdir } from "fs/promises";
import path from "path";
import { OPERATOR_ROOT } from "./config";

/** Agent identity from workspace IDENTITY.md; OpenClaw agent slots; Operator workflows */
const AGENT_WORKSPACE = process.env.AGENT_WORKSPACE ?? "/root/agent/workspace";

export interface AgentInfo {
  id: string;
  name: string;
  description?: string;
  source: "openclaw" | "workflow";
  details?: string;
}

/** Human-readable names and short descriptions for operator workflows */
const WORKFLOW_LABELS: Record<string, { name: string; desc: string }> = {
  planner: { name: "Planner", desc: "Plant nächste Schritte (LLM)" },
  critic: { name: "Critic", desc: "Bewertet System-Output (LLM)" },
  prioritize: { name: "Prioritize", desc: "Setzt Prioritäten" },
  "autopilot-infra": { name: "Autopilot Infra", desc: "Überwacht Infrastruktur, startet Zyklen" },
  "factory-cycle": { name: "Factory Cycle", desc: "Discover → Match → Pack → Deliver" },
  "opportunity-discovery": { name: "Opportunity Discovery", desc: "Findet Opportunities (HN, News)" },
  "opportunity-ingest": { name: "Opportunity Ingest", desc: "Schreibt Opportunities ins Backlog" },
  "opportunity-select": { name: "Opportunity Select", desc: "Wählt Opportunities aus" },
  "opportunity-dispatch": { name: "Opportunity Dispatch", desc: "Erstellt Jobs aus ausgewählten" },
  "tool-idea": { name: "Tool Idea", desc: "Schlägt neue Tools vor (LLM)" },
  "tool-eval": { name: "Tool Eval", desc: "Bewertet Tools (LLM)" },
  "tool-create": { name: "Tool Create", desc: "Erstellt Tool-Skript" },
  "tool-register": { name: "Tool Register", desc: "Registriert Tool" },
  "tool-use": { name: "Tool Use", desc: "Führt Tool aus" },
  "tool-improve": { name: "Tool Improve", desc: "Verbessert Tool" },
  "tool-backlog-add": { name: "Tool Backlog Add", desc: "Fügt Backlog-Eintrag hinzu" },
  "tool-backlog-improve": { name: "Tool Backlog Improve", desc: "Verbessert Backlog" },
  signals: { name: "Signals", desc: "Sammelt System-Signale (Disk, Load)" },
  "infra-status": { name: "Infra Status", desc: "Status-Check Infrastruktur" },
  "propose-infra": { name: "Propose Infra", desc: "Vorschläge für Infra" },
  "knowledge-commit": { name: "Knowledge Commit", desc: "Schreibt ins Knowledge-Base" },
  "goal-progress": { name: "Goal Progress", desc: "Fortschritt zu Goals" },
  "queue-run": { name: "Queue Run", desc: "Führt Queue-Jobs aus" },
  "queue-notify": { name: "Queue Notify", desc: "Benachrichtigung für Queue" },
  "product-spec": { name: "Product Spec", desc: "Erstellt Produkt-Spec" },
  "product-skeleton": { name: "Product Skeleton", desc: "Erstellt Produkt-Grundgerüst" },
  "product-feature-jobs": { name: "Product Feature Jobs", desc: "Feature-Jobs für Produkt" },
};

export async function listAgents(): Promise<AgentInfo[]> {
  const out: AgentInfo[] = [];

  // Captain = Operator / Agent-System (Brain, Workflows, Jobs) — nicht OpenClaw
  out.push({
    id: "captain",
    name: "Captain",
    description: "Agent-System: Brain, Workflows, Jobs. Läuft autonom, nicht in Telegram.",
    source: "workflow",
    details: "Operator – der andere Agent neben June.",
  });

  // June = OpenClaw, der Agent mit dem du in Telegram schreibst
  try {
    const identityPath = path.join(AGENT_WORKSPACE, "IDENTITY.md");
    const raw = await readFile(identityPath, "utf-8");
    const nameMatch = raw.match(/\*\*Name:\*\*\s*(\S+)/);
    const creatureMatch = raw.match(/\*\*Creature:\*\*\s*([^\n*]+)/);
    const vibeMatch = raw.match(/\*\*Vibe:\*\*\s*([^\n*]+)/);
    out.push({
      id: "june",
      name: nameMatch?.[1] ?? "June",
      description: creatureMatch?.[1]?.trim() ?? "Der Agent, mit dem du in Telegram schreibst.",
      source: "openclaw",
      details: vibeMatch?.[1]?.trim(),
    });
  } catch {
    out.push({
      id: "june",
      name: "June",
      description: "Der Agent, mit dem du in Telegram schreibst.",
      source: "openclaw",
    });
  }

  return out;
}

export interface WorkflowInfo {
  id: string;
  name: string;
  description: string;
}

export async function listWorkflows(): Promise<WorkflowInfo[]> {
  const out: WorkflowInfo[] = [];
  const wfPath = path.join(OPERATOR_ROOT, "workflows");
  try {
    const entries = await readdir(wfPath, { withFileTypes: true });
    for (const e of entries) {
      if (!e.isDirectory() && e.name.endsWith(".sh")) {
        const id = e.name.replace(/\.sh$/, "");
        const label = WORKFLOW_LABELS[id] ?? {
          name: id.split("-").map((s) => s.charAt(0).toUpperCase() + s.slice(1)).join(" "),
          desc: "Operator-Workflow",
        };
        out.push({ id, name: label.name, description: label.desc });
      }
    }
    out.sort((a, b) => a.name.localeCompare(b.name));
  } catch {
    //
  }
  return out;
}
