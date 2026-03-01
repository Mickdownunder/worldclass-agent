import Link from "next/link";
import { listAgents, listWorkflows, type AgentInfo, type WorkflowInfo } from "@/lib/operator/agents";
import { ALLOWED_WORKFLOWS } from "@/lib/operator/actions";

export const dynamic = "force-dynamic";

type WorkflowCategory =
  | "research"
  | "factory"
  | "tools"
  | "infra"
  | "brain"
  | "product"
  | "other";

const CATEGORY_META: Record<
  WorkflowCategory,
  { label: string; short: string; order: number }
> = {
  research: { label: "Research", short: "Forschung", order: 0 },
  brain: { label: "Brain & Qualität", short: "Planung, Bewertung", order: 1 },
  factory: { label: "Factory & Opportunity", short: "Discover, Pack, Dispatch", order: 2 },
  tools: { label: "Tools", short: "Tool-Ideen, Eval, Use", order: 3 },
  infra: { label: "Infrastruktur", short: "Status, Signals", order: 4 },
  product: { label: "Produkt", short: "Spec, Skeleton", order: 5 },
  other: { label: "Sonstige", short: "Knowledge, Goals, Queue", order: 6 },
};

function getWorkflowCategory(id: string): WorkflowCategory {
  if (id === "research-init" || id === "research-cycle") return "research";
  if (id === "planner" || id === "critic" || id === "prioritize") return "brain";
  if (id === "factory-cycle" || id.startsWith("opportunity-")) return "factory";
  if (id.startsWith("tool-")) return "tools";
  if (
    id === "infra-status" ||
    id === "signals" ||
    id === "autopilot-infra" ||
    id === "propose-infra"
  )
    return "infra";
  if (id.startsWith("product-")) return "product";
  return "other";
}

function AgentCard({ agent }: { agent: AgentInfo }) {
  const isCaptain = agent.id === "captain";
  const isJune = agent.id === "june";
  return (
    <div
      className="rounded-xl border p-6 transition-colors hover:border-tron-accent/40"
      style={{
        borderColor: "var(--tron-border)",
        background:
          isCaptain || isJune
            ? "linear-gradient(135deg, color-mix(in srgb, var(--tron-accent) 6%, transparent) 0%, var(--tron-bg-panel) 100%)"
            : "var(--tron-bg-panel)",
      }}
    >
      <div className="flex items-start gap-4">
        <div
          className="flex h-12 w-12 shrink-0 items-center justify-center rounded-lg text-xl"
          style={{
            background: isCaptain
              ? "color-mix(in srgb, var(--tron-accent) 18%, transparent)"
              : isJune
                ? "color-mix(in srgb, var(--tron-success, #22c55e) 18%, transparent)"
                : "var(--tron-bg)",
            border: "1px solid var(--tron-border)",
          }}
        >
          {isCaptain ? "⚙" : isJune ? "💬" : "•"}
        </div>
        <div className="min-w-0 flex-1">
          <div className="flex flex-wrap items-center gap-2">
            <h3 className="text-lg font-semibold" style={{ color: "var(--tron-text)" }}>
              {agent.name}
            </h3>
            <span
              className="rounded px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wider"
              style={{
                background:
                  agent.source === "openclaw"
                    ? "color-mix(in srgb, var(--tron-success, #22c55e) 15%, transparent)"
                    : "color-mix(in srgb, var(--tron-accent) 15%, transparent)",
                color: "var(--tron-text)",
                border: "1px solid var(--tron-border)",
              }}
            >
              {agent.source === "openclaw" ? "OpenClaw · Telegram" : "Operator"}
            </span>
          </div>
          {agent.description && (
            <p className="mt-1.5 text-sm leading-snug" style={{ color: "var(--tron-text-muted)" }}>
              {agent.description}
            </p>
          )}
          {agent.details && (
            <p className="mt-1 text-xs" style={{ color: "var(--tron-text-dim)" }}>
              {agent.details}
            </p>
          )}
          <div className="mt-4 rounded-lg border py-2.5 px-3" style={{ borderColor: "var(--tron-border)", background: "var(--tron-bg)" }}>
            <div className="text-[10px] font-semibold uppercase tracking-wider" style={{ color: "var(--tron-text-dim)" }}>
              {isCaptain ? "Einsatz" : "Nutzt"}
            </div>
            <ul className="mt-1.5 space-y-0.5 text-sm" style={{ color: "var(--tron-text)" }}>
              {isCaptain && (
                <>
                  <li><strong>Brain</strong> — Perceive → Understand → Think → Decide → Act → Reflect</li>
                  <li><strong>Workflows</strong> — alle unten gelisteten Skripte (op job new + op run)</li>
                  <li><strong>Plumber</strong> — Self-Healing bei wiederholten Workflow-Fehlern</li>
                </>
              )}
              {isJune && (
                <>
                  <li><strong>Research</strong> — /research-start, /research-cycle, /research-go, /research-feedback</li>
                  <li><strong>Jobs</strong> — startet Workflows über op (wie Captain)</li>
                </>
              )}
            </ul>
          </div>
        </div>
      </div>
    </div>
  );
}

function WorkflowRow({
  workflow,
  allowedFromUi,
}: {
  workflow: WorkflowInfo;
  allowedFromUi: boolean;
}) {
  return (
    <tr
      className="border-b transition-colors last:border-b-0 hover:bg-tron-accent/5"
      style={{ borderColor: "var(--tron-border)" }}
    >
      <td className="py-3 pr-3">
        <span className="font-medium" style={{ color: "var(--tron-text)" }}>
          {workflow.name}
        </span>
      </td>
      <td className="py-3 pr-3 font-mono text-xs" style={{ color: "var(--tron-text-dim)" }}>
        {workflow.id}
      </td>
      <td className="py-3 pr-3 text-sm" style={{ color: "var(--tron-text-muted)" }}>
        {workflow.description}
      </td>
      <td className="py-3 pl-3 text-right">
        {allowedFromUi && (
          <span
            className="inline-block rounded px-2 py-0.5 text-[10px] font-semibold"
            style={{
              background: "color-mix(in srgb, var(--tron-accent) 20%, transparent)",
              color: "var(--tron-accent)",
              border: "1px solid color-mix(in srgb, var(--tron-accent) 40%, transparent)",
            }}
          >
            Quick-Action
          </span>
        )}
      </td>
    </tr>
  );
}

export default async function AgentsPage() {
  const [agents, workflows] = await Promise.all([listAgents(), listWorkflows()]);

  const byCategory = workflows.reduce<Record<WorkflowCategory, WorkflowInfo[]>>(
    (acc, w) => {
      const cat = getWorkflowCategory(w.id);
      if (!acc[cat]) acc[cat] = [];
      acc[cat].push(w);
      return acc;
    },
    {} as Record<WorkflowCategory, WorkflowInfo[]>
  );

  const orderedCategories = (Object.entries(CATEGORY_META) as [WorkflowCategory, typeof CATEGORY_META[WorkflowCategory]][])
    .sort((a, b) => a[1].order - b[1].order)
    .filter(([cat]) => (byCategory[cat]?.length ?? 0) > 0);

  return (
    <div className="space-y-8 animate-fade-in">
      {/* ── Wer entscheidet was? Du musst nichts wissen. ───────── */}
      <div
        className="rounded-xl border p-5"
        style={{
          borderColor: "color-mix(in srgb, var(--tron-accent) 35%, transparent)",
          background: "linear-gradient(135deg, color-mix(in srgb, var(--tron-accent) 8%, transparent) 0%, var(--tron-bg-panel) 100%)",
        }}
      >
        <h2 className="text-sm font-bold uppercase tracking-wider" style={{ color: "var(--tron-accent)" }}>
          Du entscheidest nicht – das System entscheidet
        </h2>
        <p className="mt-2 text-sm leading-relaxed" style={{ color: "var(--tron-text)" }}>
          Du gibst nur die <strong>Forschungsfrage</strong> oder das <strong>Ziel</strong> ein. Welcher Workflow wann läuft, entscheidet der <strong>Brain</strong>: Er sieht offene Research-Projekte, nutzt Memory und Principles und startet von sich aus <em>research-cycle</em>, <em>planner</em>, <em>factory-cycle</em> oder was gerade passt. Du klickst nicht auf einzelne Workflows – du startest Research (eine Frage) oder einen Brain Cycle (Brain wählt die nächste Aktion).
        </p>
        <ul className="mt-3 space-y-1 text-sm" style={{ color: "var(--tron-text-muted)" }}>
          <li><strong className="text-tron-text">Research:</strong> Frage eingeben → System legt Projekt an und führt alle Phasen bis zum Report (oder du lässt den Brain research-cycle für offene Projekte wählen).</li>
          <li><strong className="text-tron-text">Alles andere:</strong> Brain Cycle starten → Brain nutzt State + Memory, entscheidet die nächste Aktion und startet den passenden Workflow. Du musst nicht wissen, welcher das ist.</li>
        </ul>
      </div>

      {/* ── Header ────────────────────────────────────────────── */}
      <div className="flex flex-wrap items-end justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold tracking-tight" style={{ color: "var(--tron-text)" }}>
            Agents & Workflows
          </h1>
          <p className="mt-1 max-w-xl text-sm" style={{ color: "var(--tron-text-muted)" }}>
            Wer im System läuft (Captain = Brain + Workflows, June = Telegram) und welche Workflows der Brain starten kann – zur Übersicht, nicht zum Auswählen.
          </p>
        </div>
      </div>

      {/* ── Agenten ────────────────────────────────────────────── */}
      <section>
        <h2 className="mb-3 text-xs font-semibold uppercase tracking-wider" style={{ color: "var(--tron-text-dim)" }}>
          Haupt-Agenten
        </h2>
        <div className="grid gap-5 sm:grid-cols-2">
          {agents.map((a) => (
            <AgentCard key={a.id} agent={a} />
          ))}
        </div>
      </section>

      {/* ── Workflows nach Kategorie ───────────────────────────── */}
      <section>
        <h2 className="mb-3 text-xs font-semibold uppercase tracking-wider" style={{ color: "var(--tron-text-dim)" }}>
          Captain’s Workflows · nach Kategorie
        </h2>
        <p className="mb-4 text-sm" style={{ color: "var(--tron-text-muted)" }}>
          Alle <span className="font-mono text-tron-accent">{workflows.length}</span> Workflows kann der Brain starten. <strong>Quick-Action</strong> = zusätzlich im Command Center als Button (optional); du musst sie nicht nutzen – der Brain wählt automatisch.
        </p>

        <div className="space-y-6">
          {orderedCategories.map(([cat]) => {
            const meta = CATEGORY_META[cat];
            const list = byCategory[cat] ?? [];
            return (
              <div
                key={cat}
                className="rounded-xl border overflow-hidden"
                style={{ borderColor: "var(--tron-border)", background: "var(--tron-bg-panel)" }}
              >
                <div
                  className="flex items-center gap-2 px-4 py-2.5"
                  style={{ borderBottom: "1px solid var(--tron-border)", background: "var(--tron-bg)" }}
                >
                  <span className="font-semibold text-sm" style={{ color: "var(--tron-accent)" }}>
                    {meta.label}
                  </span>
                  <span className="text-xs" style={{ color: "var(--tron-text-dim)" }}>
                    {meta.short}
                  </span>
                  <span className="ml-auto font-mono text-[10px]" style={{ color: "var(--tron-text-dim)" }}>
                    {list.length} Workflow{list.length !== 1 ? "s" : ""}
                  </span>
                </div>
                <div className="overflow-x-auto">
                  <table className="w-full min-w-[520px] text-sm">
                    <thead>
                      <tr className="text-left text-[10px] font-semibold uppercase tracking-wider" style={{ color: "var(--tron-text-muted)" }}>
                        <th className="p-3">Name</th>
                        <th className="p-3">ID</th>
                        <th className="p-3">Beschreibung</th>
                        <th className="p-3 w-24 text-right">Quick-Action</th>
                      </tr>
                    </thead>
                    <tbody>
                      {list.map((w) => (
                        <WorkflowRow
                          key={w.id}
                          workflow={w}
                          allowedFromUi={ALLOWED_WORKFLOWS.has(w.id)}
                        />
                      ))}
                    </tbody>
                  </table>
                </div>
              </div>
            );
          })}
        </div>

        {workflows.length === 0 && (
          <p className="rounded-lg border border-dashed py-8 text-center text-sm" style={{ borderColor: "var(--tron-border)", color: "var(--tron-text-dim)" }}>
            Keine Workflows gefunden (workflows/*.sh).
          </p>
        )}
      </section>

      {/* ── Kurzreferenz ───────────────────────────────────────── */}
      <section
        className="rounded-lg border p-4"
        style={{ borderColor: "var(--tron-border)", background: "var(--tron-bg)" }}
      >
        <h3 className="text-xs font-semibold uppercase tracking-wider" style={{ color: "var(--tron-text-dim)" }}>
          Kurzreferenz
        </h3>
        <ul className="mt-2 space-y-1 text-xs" style={{ color: "var(--tron-text-muted)" }}>
          <li><strong className="text-tron-text">Research:</strong> Auf der Research-Seite Frage eingeben → System startet und führt bis zum Report. Kein Workflow-Auswählen.</li>
          <li><strong className="text-tron-text">Brain:</strong> <Link href="/memory" className="underline hover:text-tron-accent">Memory & Graph</Link> — Brain-Status, Episoden, Principles. Brain Cycle = Brain wählt die nächste Aktion (Workflow) selbst.</li>
          <li><strong className="text-tron-text">Quick-Actions:</strong> Nur Optionen im Command Center; der Brain entscheidet sonst automatisch, welcher Workflow läuft.</li>
        </ul>
      </section>
    </div>
  );
}
