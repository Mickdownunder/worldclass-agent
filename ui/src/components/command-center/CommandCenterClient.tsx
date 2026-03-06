"use client";

import Link from "next/link";
import { useEffect, useMemo, useState, type CSSProperties } from "react";
import type {
  CampaignSummary,
  CommandCenterData,
  CommandMissionSummary,
  CommandMissionTask,
  PortfolioSummary,
} from "@/lib/operator/command-center";

type ActionName = "create" | "show" | "pause" | "resume" | "retry" | "replan";

type CommandCenterClientProps = {
  initialData: CommandCenterData;
  initialSelectedMissionId?: string;
};

const QUICK_TEMPLATES = [
  {
    label: "Status",
    objective: "Primary control-plane status validation",
    requestText: "status check",
  },
  {
    label: "Mini",
    objective: "Primary control-plane mini validation",
    requestText: "mini_fast",
  },
  {
    label: "Research",
    objective: "Primary control-plane research validation",
    requestText: "research cycle validation on current operator stack",
  },
];

export function CommandCenterClient({ initialData, initialSelectedMissionId }: CommandCenterClientProps) {
  const [data, setData] = useState(initialData);
  const [selectedMissionId, setSelectedMissionId] = useState(initialSelectedMissionId ?? initialData.missions[0]?.id ?? "");
  const [objective, setObjective] = useState(QUICK_TEMPLATES[0].objective);
  const [requestText, setRequestText] = useState(QUICK_TEMPLATES[0].requestText);
  const [executeImmediately, setExecuteImmediately] = useState(true);
  const [reason, setReason] = useState("");
  const [message, setMessage] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState<ActionName | null>(null);

  const selectedMission = useMemo(
    () => data.missions.find((mission) => mission.id === selectedMissionId) ?? data.missions[0],
    [data.missions, selectedMissionId],
  );

  const focusMission = useMemo(() => pickFocusMission(data.missions), [data.missions]);
  const blockedMissions = useMemo(() => data.missions.filter((mission) => mission.lifecycle === "blocked"), [data.missions]);
  const decisionMissions = useMemo(
    () => data.missions.filter((mission) => mission.lifecycle === "awaiting_next_test" || mission.lifecycle === "blocked"),
    [data.missions],
  );
  const recentCompleted = useMemo(
    () => data.missions.find((mission) => mission.lifecycle === "done"),
    [data.missions],
  );

  useEffect(() => {
    if (!selectedMissionId && data.missions[0]?.id) {
      setSelectedMissionId(data.missions[0].id);
    }
  }, [data.missions, selectedMissionId]);

  useEffect(() => {
    const active = data.missions.some(
      (mission) => mission.lifecycle === "active" || mission.lifecycle === "awaiting_next_test" || mission.status === "planned",
    );
    if (!active) return;
    const interval = window.setInterval(() => {
      void refreshData(setData, setError);
    }, 10000);
    return () => window.clearInterval(interval);
  }, [data.missions]);

  async function runAction(action: ActionName, overrides: Record<string, unknown> = {}) {
    setBusy(action);
    setError(null);
    setMessage(null);
    try {
      const response = await fetch("/api/command-center", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          action,
          missionId: selectedMission?.id,
          objective,
          requestText,
          reason,
          execute: executeImmediately,
          ...overrides,
        }),
      });
      const result = await response.json();
      if (!response.ok || !result.ok) {
        throw new Error(result.error ?? "Command action failed");
      }
      if (result.data) {
        setData(result.data as CommandCenterData);
      }
      if (result.mission?.id) {
        setSelectedMissionId(result.mission.id);
      }
      setMessage(actionMessage(action, result.mission?.id));
      if (action !== "replan") {
        setReason("");
      }
    } catch (actionError) {
      setError(String((actionError as Error).message));
    } finally {
      setBusy(null);
    }
  }

  function applyTemplate(label: string) {
    const template = QUICK_TEMPLATES.find((entry) => entry.label === label);
    if (!template) return;
    setObjective(template.objective);
    setRequestText(template.requestText);
  }

  return (
    <div className="space-y-6 animate-fade-in">
      <section
        className="rounded-[28px] p-6 md:p-8"
        style={{
          border: "1px solid var(--tron-border-strong)",
          background:
            "linear-gradient(135deg, color-mix(in srgb, var(--tron-accent) 8%, transparent) 0%, color-mix(in srgb, var(--tron-bg-panel) 94%, transparent) 58%, var(--tron-bg-panel) 100%)",
          boxShadow: "0 18px 48px color-mix(in srgb, var(--tron-glow-accent) 55%, transparent)",
        }}
      >
        <div className="grid gap-6 xl:grid-cols-[1.15fr_0.85fr] xl:items-start">
          <div className="space-y-4">
            <div
              className="inline-flex items-center gap-2 rounded-full px-3 py-1 text-[11px] font-semibold uppercase tracking-[0.22em]"
              style={{
                background: "color-mix(in srgb, var(--tron-accent) 12%, transparent)",
                color: "var(--tron-accent)",
                border: "1px solid color-mix(in srgb, var(--tron-accent) 28%, transparent)",
              }}
            >
              Master View
            </div>
            <div>
              <h1 className="text-3xl font-semibold tracking-tight" style={{ color: "var(--tron-text)" }}>
                June Control Center
              </h1>
              <p className="mt-3 max-w-2xl text-sm leading-6" style={{ color: "var(--tron-text-muted)" }}>
                Diese Sicht sagt dir in Klartext, woran June gerade arbeitet, wo Entscheidungen offen sind und was als Nächstes
                passieren sollte. Technische Rohdaten sind weiter unten nur noch optional sichtbar.
              </p>
            </div>
            <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-3">
              <SummaryCard
                label="June arbeitet gerade an"
                value={focusMission ? focusMission.objective : "Keine aktive Mission"}
                hint={focusMission ? describeMissionState(focusMission) : "System ist gerade idle"}
              />
              <SummaryCard
                label="Braucht deine Entscheidung"
                value={decisionMissions[0] ? decisionMissions[0].objective : "Nichts offen"}
                hint={decisionMissions[0] ? describeNextStep(decisionMissions[0]) : "Keine offene Freigabe oder Folgeentscheidung"}
              />
              <SummaryCard
                label="Zuletzt sauber abgeschlossen"
                value={recentCompleted ? recentCompleted.objective : "Noch kein abgeschlossener Lauf"}
                hint={recentCompleted ? (recentCompleted.envelope?.overall ?? recentCompleted.status) : "Wird angezeigt, sobald eine Mission final done ist"}
              />
            </div>
          </div>

          <div className="grid gap-3 sm:grid-cols-2">
            <StatTile label="Missionen gesamt" value={String(data.stats.totalMissions)} />
            <StatTile label="Aktiv oder offen" value={String(data.stats.activeMissions)} />
            <StatTile label="Brauchen Eingriff" value={String(blockedMissions.length)} />
            <StatTile label="Portfolios" value={String(data.stats.portfolios)} />
          </div>
        </div>
      </section>

      <div className="grid gap-6 xl:grid-cols-[1.05fr_0.95fr]">
        <section className="space-y-6">
          <section className="rounded-[24px] p-5 md:p-6" style={panelStyle}>
            <div className="flex flex-wrap items-start justify-between gap-4">
              <div>
                <div className="text-[11px] font-semibold uppercase tracking-[0.28em]" style={{ color: "var(--tron-text-dim)" }}>
                  Neue Mission starten
                </div>
                <p className="mt-2 text-sm" style={{ color: "var(--tron-text-muted)" }}>
                  Nutze Presets für kurze Standardchecks oder formuliere einen eigenen Auftrag für June.
                </p>
              </div>
              <div className="flex flex-wrap gap-2">
                {QUICK_TEMPLATES.map((template) => (
                  <button
                    key={template.label}
                    type="button"
                    onClick={() => applyTemplate(template.label)}
                    className="rounded-full px-3 py-1.5 text-xs font-semibold"
                    style={secondaryButtonStyle}
                  >
                    {template.label}
                  </button>
                ))}
              </div>
            </div>

            <div className="mt-5 grid gap-4">
              <label className="grid gap-2 text-sm">
                <span style={{ color: "var(--tron-text-muted)" }}>Worum soll June sich kümmern?</span>
                <input
                  value={objective}
                  onChange={(event) => setObjective(event.target.value)}
                  className="rounded-2xl px-4 py-3 outline-none"
                  style={fieldStyle}
                  placeholder="Primary control-plane research validation"
                  suppressHydrationWarning
                />
              </label>
              <label className="grid gap-2 text-sm">
                <span style={{ color: "var(--tron-text-muted)" }}>Konkreter Auftrag / Parameter</span>
                <textarea
                  value={requestText}
                  onChange={(event) => setRequestText(event.target.value)}
                  className="min-h-[108px] rounded-2xl px-4 py-3 outline-none"
                  style={fieldStyle}
                  placeholder="mini_fast oder ein klarer Research-Auftrag"
                  suppressHydrationWarning
                />
              </label>
              <label className="inline-flex items-center gap-3 text-sm" style={{ color: "var(--tron-text)" }}>
                <input
                  type="checkbox"
                  checked={executeImmediately}
                  onChange={(event) => setExecuteImmediately(event.target.checked)}
                  suppressHydrationWarning
                />
                Nach dem Anlegen sofort ausführen
              </label>
              <div className="flex flex-wrap items-center gap-3">
                <ActionButton
                  label={busy === "create" ? "Starte..." : "Mission starten"}
                  busy={busy === "create"}
                  tone="primary"
                  onClick={() => runAction("create", { missionId: undefined })}
                />
                <button
                  type="button"
                  onClick={() => void refreshData(setData, setError)}
                  className="rounded-full px-4 py-2 text-sm font-medium"
                  style={secondaryButtonStyle}
                >
                  Aktualisieren
                </button>
              </div>
            </div>
          </section>

          <section className="rounded-[24px] p-5 md:p-6" style={panelStyle}>
            <div className="flex items-center justify-between gap-4">
              <div>
                <div className="text-[11px] font-semibold uppercase tracking-[0.28em]" style={{ color: "var(--tron-text-dim)" }}>
                  Missionen im Klartext
                </div>
                <p className="mt-2 text-sm" style={{ color: "var(--tron-text-muted)" }}>
                  Oben stehen die wichtigsten Missionen. IDs sind nur noch Referenzen, nicht die Hauptinformation.
                </p>
              </div>
              {selectedMission && <ToneBadge value={humanOverall(selectedMission)} kind="status" />}
            </div>

            <div className="mt-4 grid gap-3">
              {data.missions.map((mission) => {
                const active = mission.id === selectedMission?.id;
                return (
                  <button
                    key={mission.id}
                    type="button"
                    onClick={() => setSelectedMissionId(mission.id)}
                    className="grid gap-3 rounded-[22px] p-4 text-left transition-colors"
                    style={{
                      border: active ? "1px solid var(--tron-accent)" : "1px solid var(--tron-border)",
                      background: active ? "color-mix(in srgb, var(--tron-accent) 8%, var(--tron-bg-panel))" : "var(--tron-bg)",
                    }}
                  >
                    <div className="flex flex-wrap items-start justify-between gap-3">
                      <div className="min-w-0 flex-1">
                        <div className="text-base font-semibold" style={{ color: "var(--tron-text)" }}>
                          {mission.objective}
                        </div>
                        <div className="mt-1 text-sm" style={{ color: "var(--tron-text-muted)" }}>
                          {describeMissionState(mission)}
                        </div>
                      </div>
                      <div className="shrink-0">
                        <ToneBadge value={humanOverall(mission)} kind="status" />
                      </div>
                    </div>
                    <div className="grid gap-2 text-sm md:grid-cols-3">
                      <PlainFact label="Als Nächstes" value={describeNextStep(mission)} />
                      <PlainFact label="Typ" value={friendlyPlan(mission.plan)} />
                      <PlainFact label="ID" value={mission.id} mono />
                    </div>
                  </button>
                );
              })}
            </div>
          </section>
        </section>

        <aside className="space-y-6">
          <section className="rounded-[24px] p-5 md:p-6" style={panelStyle}>
            <div className="flex flex-wrap items-start justify-between gap-3">
              <div>
                <div className="text-[11px] font-semibold uppercase tracking-[0.28em]" style={{ color: "var(--tron-text-dim)" }}>
                  Ausgewählte Mission
                </div>
                {selectedMission ? (
                  <>
                    <h2 className="mt-2 text-xl font-semibold" style={{ color: "var(--tron-text)" }}>
                      {selectedMission.objective}
                    </h2>
                    <p className="mt-2 text-sm leading-6" style={{ color: "var(--tron-text-muted)" }}>
                      {describeMissionForHuman(selectedMission)}
                    </p>
                  </>
                ) : (
                  <p className="mt-2 text-sm" style={{ color: "var(--tron-text-muted)" }}>Keine Mission ausgewählt.</p>
                )}
              </div>
              {selectedMission && <ToneBadge value={humanLifecycle(selectedMission.lifecycle)} kind="mission" />}
            </div>

            {selectedMission && (
              <>
                <div className="mt-5 grid gap-3 sm:grid-cols-2">
                  <DetailTile label="June sagt" value={describeMissionState(selectedMission)} />
                  <DetailTile label="Nächster Schritt" value={describeNextStep(selectedMission)} />
                  <DetailTile label="Letzter Lauf" value={selectedMission.envelope?.overall ?? "noch kein Ergebnis"} />
                  <DetailTile label="Atlas" value={selectedMission.envelope?.atlas_overall ?? "n/a"} />
                </div>

                <div className="mt-5 grid gap-2">
                  <label className="grid gap-2 text-sm">
                    <span style={{ color: "var(--tron-text-muted)" }}>Notiz / Grund für die Aktion</span>
                    <input
                      value={reason}
                      onChange={(event) => setReason(event.target.value)}
                      className="rounded-2xl px-4 py-3 outline-none"
                      style={fieldStyle}
                      placeholder="z. B. pausieren, neu planen oder wiederholen"
                      suppressHydrationWarning
                    />
                  </label>
                  <div className="flex flex-wrap gap-2">
                    <ActionButton label="Aktualisieren" busy={busy === "show"} onClick={() => runAction("show")} />
                    <ActionButton label="Pausieren" busy={busy === "pause"} onClick={() => runAction("pause")} />
                    <ActionButton label="Fortsetzen" busy={busy === "resume"} onClick={() => runAction("resume")} />
                    <ActionButton label="Erneut versuchen" busy={busy === "retry"} onClick={() => runAction("retry")} />
                  </div>
                </div>

                <div className="mt-5 grid gap-2">
                  <label className="grid gap-2 text-sm">
                    <span style={{ color: "var(--tron-text-muted)" }}>Neu planen mit diesem Auftrag</span>
                    <textarea
                      value={requestText}
                      onChange={(event) => setRequestText(event.target.value)}
                      className="min-h-[96px] rounded-2xl px-4 py-3 outline-none"
                      style={fieldStyle}
                      suppressHydrationWarning
                    />
                  </label>
                  <ActionButton label="Neu planen" busy={busy === "replan"} tone="primary" onClick={() => runAction("replan")} />
                </div>

                <div className="mt-5 flex flex-wrap items-center justify-between gap-3 rounded-[20px] p-4" style={{ border: "1px solid var(--tron-border)", background: "var(--tron-bg)" }}>
                  <div>
                    <div className="text-sm font-semibold" style={{ color: "var(--tron-text)" }}>Tiefe Details</div>
                    <div className="mt-1 text-xs" style={{ color: "var(--tron-text-muted)" }}>
                      Für Debugging, Artefakte und den technischen Zustand dieser Mission.
                    </div>
                  </div>
                  <Link href={`/agents/command/${selectedMission.id}`} className="font-medium" style={{ color: "var(--tron-accent)" }}>
                    Missionsdetail öffnen →
                  </Link>
                </div>
              </>
            )}
          </section>

          <section className="rounded-[24px] p-5 md:p-6" style={panelStyle}>
            <div className="text-[11px] font-semibold uppercase tracking-[0.28em]" style={{ color: "var(--tron-text-dim)" }}>
              Portfolios und Campaigns
            </div>
            <p className="mt-2 text-sm" style={{ color: "var(--tron-text-muted)" }}>
              Das ist die Gruppierung der Missionen. Nur zur Orientierung, nicht für den täglichen Eingriff.
            </p>
            <div className="mt-4 grid gap-3 md:grid-cols-2">
              <CompactPortfolioPanel portfolios={data.portfolios} />
              <CompactCampaignPanel campaigns={data.campaigns} />
            </div>
          </section>

          <details className="rounded-[24px] p-5 md:p-6" style={panelStyle}>
            <summary className="cursor-pointer list-none text-sm font-semibold" style={{ color: "var(--tron-text)" }}>
              Technische Details anzeigen
            </summary>
            <div className="mt-5 space-y-6">
              <section>
                <div className="text-[11px] font-semibold uppercase tracking-[0.28em]" style={{ color: "var(--tron-text-dim)" }}>
                  Execution Graph
                </div>
                <div className="mt-4 space-y-3">
                  {selectedMission?.tasks.map((task) => <TaskRow key={task.task_id} task={task} />)}
                </div>
              </section>

              <section>
                <div className="text-[11px] font-semibold uppercase tracking-[0.28em]" style={{ color: "var(--tron-text-dim)" }}>
                  Decision / Envelope
                </div>
                <div className="mt-4 grid gap-3">
                  <DetailTile label="Overall" value={selectedMission?.decision?.overall ?? selectedMission?.envelope?.overall ?? "n/a"} />
                  <DetailTile label="Recommendation" value={selectedMission?.envelope?.recommendation ?? "n/a"} />
                  <DetailTile label="Run Dir" value={selectedMission?.envelope?.run_dir ?? "n/a"} mono />
                  <DetailTile label="Summary File" value={selectedMission?.envelope?.summary_file ?? "n/a"} mono />
                  <DetailTile label="Campaign" value={selectedMission?.campaign_id ?? "n/a"} />
                  <DetailTile label="Portfolio" value={selectedMission?.portfolio_id ?? "n/a"} />
                </div>
              </section>
            </div>
          </details>

          {(message || error) && (
            <section
              className="rounded-[24px] p-4"
              style={{
                border: `1px solid ${error ? "color-mix(in srgb, var(--tron-error) 45%, transparent)" : "color-mix(in srgb, var(--tron-success) 35%, transparent)"}`,
                background: error
                  ? "color-mix(in srgb, var(--tron-error) 9%, var(--tron-bg-panel))"
                  : "color-mix(in srgb, var(--tron-success) 8%, var(--tron-bg-panel))",
                color: error ? "var(--tron-error)" : "var(--tron-success)",
              }}
            >
              {error ?? message}
            </section>
          )}
        </aside>
      </div>
    </div>
  );
}

function SummaryCard({ label, value, hint }: { label: string; value: string; hint: string }) {
  return (
    <div className="rounded-[22px] p-4" style={{ border: "1px solid var(--tron-border)", background: "var(--tron-bg)" }}>
      <div className="text-[11px] font-semibold uppercase tracking-[0.22em]" style={{ color: "var(--tron-text-dim)" }}>{label}</div>
      <div className="mt-3 text-base font-semibold leading-6" style={{ color: "var(--tron-text)" }}>{value}</div>
      <div className="mt-2 text-xs leading-5" style={{ color: "var(--tron-text-muted)" }}>{hint}</div>
    </div>
  );
}

function CompactPortfolioPanel({ portfolios }: { portfolios: PortfolioSummary[] }) {
  return (
    <div className="space-y-3">
      {portfolios.slice(0, 4).map((portfolio) => (
        <div key={portfolio.id} className="rounded-[20px] p-4" style={{ border: "1px solid var(--tron-border)", background: "var(--tron-bg)" }}>
          <div className="text-sm font-semibold" style={{ color: "var(--tron-text)" }}>{friendlyPortfolio(portfolio.id)}</div>
          <div className="mt-1 text-xs" style={{ color: "var(--tron-text-muted)" }}>{portfolio.campaigns} Campaigns</div>
        </div>
      ))}
    </div>
  );
}

function CompactCampaignPanel({ campaigns }: { campaigns: CampaignSummary[] }) {
  return (
    <div className="space-y-3">
      {campaigns.slice(0, 4).map((campaign) => (
        <div key={campaign.id} className="rounded-[20px] p-4" style={{ border: "1px solid var(--tron-border)", background: "var(--tron-bg)" }}>
          <div className="text-sm font-semibold" style={{ color: "var(--tron-text)" }}>{campaign.objective}</div>
          <div className="mt-1 text-xs" style={{ color: "var(--tron-text-muted)" }}>{friendlyPlan(campaign.plan)} · {campaign.latest?.next_action ?? "n/a"}</div>
        </div>
      ))}
    </div>
  );
}

function StatTile({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-[22px] px-4 py-4" style={{ border: "1px solid var(--tron-border)", background: "color-mix(in srgb, var(--tron-bg-panel) 72%, var(--tron-bg))" }}>
      <div className="text-[11px] font-semibold uppercase tracking-[0.22em]" style={{ color: "var(--tron-text-dim)" }}>{label}</div>
      <div className="mt-3 text-2xl font-semibold" style={{ color: "var(--tron-text)" }}>{value}</div>
    </div>
  );
}

function PlainFact({ label, value, mono = false }: { label: string; value: string; mono?: boolean }) {
  return (
    <div>
      <div className="text-[11px] font-semibold uppercase tracking-[0.16em]" style={{ color: "var(--tron-text-dim)" }}>{label}</div>
      <div className={`mt-1 text-sm ${mono ? "font-mono" : ""}`} style={{ color: "var(--tron-text)" }}>{value}</div>
    </div>
  );
}

function DetailTile({ label, value, mono = false }: { label: string; value: string; mono?: boolean }) {
  return (
    <div className="rounded-[20px] p-4" style={{ border: "1px solid var(--tron-border)", background: "var(--tron-bg)" }}>
      <div className="text-[11px] font-semibold uppercase tracking-[0.22em]" style={{ color: "var(--tron-text-dim)" }}>{label}</div>
      <div className={`mt-2 break-all text-sm ${mono ? "font-mono" : ""}`} style={{ color: "var(--tron-text)" }}>{value}</div>
    </div>
  );
}

function TaskRow({ task }: { task: CommandMissionTask }) {
  return (
    <div className="rounded-[18px] p-3" style={{ border: "1px solid var(--tron-border)", background: "var(--tron-bg)" }}>
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0 flex-1">
          <div className="text-sm font-semibold" style={{ color: "var(--tron-text)" }}>{task.task_id}</div>
          <div className="mt-1 text-xs leading-5" style={{ color: "var(--tron-text-muted)" }}>{task.description}</div>
        </div>
        <ToneBadge value={task.status} kind="mission" />
      </div>
      {task.depends_on.length > 0 && (
        <div className="mt-2 text-[11px]" style={{ color: "var(--tron-text-dim)" }}>
          depends on: {task.depends_on.join(", ")}
        </div>
      )}
    </div>
  );
}

function ToneBadge({ value, kind }: { value: string; kind: "status" | "mission" }) {
  const normalized = value.toUpperCase();
  const color =
    normalized === "PASS" || normalized === "DONE"
      ? "var(--tron-success)"
      : normalized === "FAIL" || normalized === "FAILED" || normalized === "BLOCKED"
        ? "var(--tron-error)"
        : normalized === "RUNNING" || normalized === "PLANNED" || normalized === "ACTIVE" || normalized === "ARBEITET"
          ? "var(--tron-accent)"
          : "var(--tron-text-muted)";

  return (
    <span
      className="inline-flex min-w-[72px] items-center justify-center rounded-full px-3 py-1 text-[11px] font-semibold uppercase tracking-[0.14em]"
      style={{
        color,
        background: `color-mix(in srgb, ${color} 12%, transparent)`,
        border: `1px solid color-mix(in srgb, ${color} 28%, transparent)`,
      }}
    >
      {kind === "mission" ? value : normalized}
    </span>
  );
}

function pickFocusMission(missions: CommandMissionSummary[]) {
  return (
    missions.find((mission) => mission.lifecycle === "active") ??
    missions.find((mission) => mission.lifecycle === "awaiting_next_test") ??
    missions.find((mission) => mission.status === "planned") ??
    missions[0]
  );
}

function describeMissionState(mission: CommandMissionSummary) {
  switch (mission.lifecycle) {
    case "active":
      return `June arbeitet gerade an einem ${friendlyPlan(mission.plan)}-Lauf.`;
    case "awaiting_next_test":
      return "Der letzte Lauf war erfolgreich, June empfiehlt jetzt den nächsten Test.";
    case "done":
      return "Diese Mission ist abgeschlossen.";
    case "blocked":
      return "Diese Mission braucht Eingriff oder eine Neuplanung.";
    case "paused":
      return "Diese Mission ist absichtlich pausiert.";
    case "planned":
      return "Diese Mission ist vorbereitet und wartet auf die Ausführung.";
    default:
      return "Der Zustand dieser Mission ist aktuell nicht klar klassifiziert.";
  }
}

function describeNextStep(mission: CommandMissionSummary) {
  const next = mission.decision?.next_action ?? "n/a";
  switch (next) {
    case "new_test":
      return "June empfiehlt einen weiteren Test";
    case "stop":
      return "Keine Folgeaktion nötig";
    case "retry":
      return "Erneut versuchen";
    case "execute":
      return "Bereit zur Ausführung";
    case "resume":
      return "Kann fortgesetzt werden";
    default:
      return next;
  }
}

function describeMissionForHuman(mission: CommandMissionSummary) {
  const run = mission.envelope?.overall ? `Letztes Ergebnis: ${mission.envelope.overall}.` : "Es liegt noch kein Lauf-Ergebnis vor.";
  return `${describeMissionState(mission)} ${run} ${describeNextStep(mission)}.`;
}

function humanOverall(mission: CommandMissionSummary) {
  if (mission.envelope?.overall === "PASS" && mission.lifecycle === "awaiting_next_test") {
    return "OPEN";
  }
  return mission.envelope?.overall ?? humanLifecycle(mission.lifecycle);
}

function humanLifecycle(value: CommandMissionSummary["lifecycle"]) {
  switch (value) {
    case "awaiting_next_test":
      return "offen";
    case "active":
      return "arbeitet";
    case "done":
      return "done";
    case "paused":
      return "pausiert";
    case "blocked":
      return "blockiert";
    case "planned":
      return "bereit";
    default:
      return "unklar";
  }
}

function friendlyPlan(plan: string) {
  switch (plan) {
    case "status":
      return "Status-Check";
    case "mini":
      return "Mini-Test";
    case "research":
      return "Research-Lauf";
    case "full":
      return "Vollständiger Lauf";
    default:
      return plan;
  }
}

function friendlyPortfolio(portfolioId: string) {
  return portfolioId.replace(/^portfolio_/, "").replace(/_/g, " ");
}

function ActionButton({
  label,
  busy,
  onClick,
  tone = "secondary",
}: {
  label: string;
  busy: boolean;
  onClick: () => void;
  tone?: "primary" | "secondary";
}) {
  return (
    <button
      type="button"
      disabled={busy}
      onClick={onClick}
      className="rounded-full px-4 py-2 text-sm font-semibold disabled:opacity-50"
      style={tone === "primary" ? primaryButtonStyle : secondaryButtonStyle}
    >
      {label}
    </button>
  );
}

async function refreshData(
  setData: (data: CommandCenterData) => void,
  setError: (message: string | null) => void,
) {
  try {
    const response = await fetch("/api/command-center", { cache: "no-store" });
    const payload = await response.json();
    if (!response.ok) {
      throw new Error(payload.error ?? "Refresh failed");
    }
    setData(payload as CommandCenterData);
    setError(null);
  } catch (error) {
    setError(String((error as Error).message));
  }
}

function actionMessage(action: ActionName, missionId?: string) {
  switch (action) {
    case "create":
      return `Mission ${missionId ?? ""} erstellt.`.trim();
    case "pause":
      return "Mission pausiert.";
    case "resume":
      return "Mission fortgesetzt.";
    case "retry":
      return "Mission zum erneuten Versuch markiert.";
    case "replan":
      return "Mission neu geplant.";
    case "show":
      return "Mission aktualisiert.";
  }
}

const panelStyle = {
  border: "1px solid var(--tron-border)",
  background: "var(--tron-bg-panel)",
} satisfies CSSProperties;

const fieldStyle = {
  border: "1px solid var(--tron-border)",
  background: "var(--tron-bg)",
  color: "var(--tron-text)",
} satisfies CSSProperties;

const primaryButtonStyle = {
  border: "1px solid color-mix(in srgb, var(--tron-accent) 30%, transparent)",
  background: "color-mix(in srgb, var(--tron-accent) 14%, transparent)",
  color: "var(--tron-text)",
} satisfies CSSProperties;

const secondaryButtonStyle = {
  border: "1px solid var(--tron-border)",
  background: "var(--tron-bg)",
  color: "var(--tron-text)",
} satisfies CSSProperties;
