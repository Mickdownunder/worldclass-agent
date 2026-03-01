import Link from "next/link";
import { notFound } from "next/navigation";
import {
  getResearchProject,
  getLatestReportMarkdown,
  getLatestReportPdf,
  getAudit,
  getCalibratedThresholds,
  getFollowUpProjectIds,
  type ResearchProjectDetail,
  type CalibratedThresholds,
} from "@/lib/operator/research";
import { StatusBadge } from "@/components/StatusBadge";
import { StartCycleButton } from "@/components/StartCycleButton";
import { CreateFollowupButton } from "@/components/CreateFollowupButton";
import { DeleteProjectButton } from "@/components/DeleteProjectButton";
import { ReviewPanel } from "@/components/ReviewPanel";
import { CancelRunButton } from "@/components/CancelRunButton";
import { ExecutionTree } from "@/components/ExecutionTree";
import { LiveRefresh } from "@/components/LiveRefresh";
import { LiveElapsedTimer } from "@/components/LiveElapsedTimer";
import { ActivityFeed } from "@/components/ActivityFeed";
import { CouncilRoom } from "@/components/CouncilRoom";
import { ResearchDetailTabs } from "./ResearchDetailTabs";
import { PreferredDomainsTabs } from "@/components/PreferredDomainsTabs";

export const dynamic = "force-dynamic";

function formatDate(iso: string): string {
  if (!iso) return "—";
  try {
    return new Intl.DateTimeFormat("en-US", {
      month: "short", day: "numeric", year: "numeric",
      hour: "2-digit", minute: "2-digit",
    }).format(new Date(iso));
  } catch {
    return iso;
  }
}

export default async function ResearchProjectPage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const id = (await params).id;
  const project = await getResearchProject(id);
  if (!project) notFound();

  const [markdown, pdfInfo, audit, calibratedThresholds, followUpIds] = await Promise.all([
    getLatestReportMarkdown(id),
    getLatestReportPdf(id),
    project.status === "pending_review" ? getAudit(id) : Promise.resolve(null),
    getCalibratedThresholds(),
    getFollowUpProjectIds(id),
  ]);
  const TERMINAL_STATUSES = new Set(["done", "failed", "cancelled"]);
  const isTerminal = TERMINAL_STATUSES.has(project.status) || project.status.startsWith("failed");
  let completedAt: string | undefined = project.completed_at;
  if (!completedAt && isTerminal && project.phase_timings) {
    const timings = Object.values(project.phase_timings);
    const latest = timings
      .map((t) => t.completed_at)
      .filter(Boolean)
      .sort()
      .pop();
    completedAt = latest;
  }
  const isActive = !isTerminal;

  return (
    <div className="space-y-6 animate-fade-in">
      {/* Breadcrumb */}
      <div className="flex items-center gap-2 text-[12px]" style={{ color: "var(--tron-text-dim)" }}>
        <Link href="/research" className="transition-colors hover:text-[var(--tron-accent)]">
          Research Projects
        </Link>
        <span>/</span>
        <span className="font-mono" style={{ color: "var(--tron-text-muted)" }}>{id}</span>
      </div>

      {/* ── Header Card ──────────────────────────────────────── */}
      <div
        className="rounded-lg"
        style={{ border: "1px solid var(--tron-border)", background: "var(--tron-bg-panel)" }}
      >
        {/* Top bar */}
        <div
          className="flex flex-wrap items-start justify-between gap-4 px-5 py-4"
          style={{ borderBottom: "1px solid var(--tron-border)" }}
        >
          <div className="min-w-0 flex-1 flex flex-wrap items-center gap-2">
            <h1 className="text-lg font-semibold leading-snug" style={{ color: "var(--tron-text)" }}>
              {project.question || "Untitled Research"}
            </h1>
            <LiveRefresh enabled={isActive} intervalMs={5000} showIndicator={true} projectId={project.id} />
            <div className="w-full mt-1 flex flex-wrap items-center gap-2">
              <span className="font-mono text-[11px]" style={{ color: "var(--tron-text-dim)" }}>
                {id}
              </span>
              {project.parent_project_id && (
                <span className="text-[11px]" style={{ color: "var(--tron-text-muted)" }}>
                  Follow-up von{" "}
                  <Link href={`/research/${project.parent_project_id}`} className="font-mono text-tron-accent hover:underline">
                    {project.parent_project_id}
                  </Link>
                </span>
              )}
              {followUpIds.length > 0 && (
                <span className="text-[11px]" style={{ color: "var(--tron-text-muted)" }}>
                  Follow-up-Projekte:{" "}
                  {followUpIds.map((fid) => (
                    <Link key={fid} href={`/research/${fid}`} className="font-mono text-tron-accent hover:underline mr-1">
                      {fid}
                    </Link>
                  ))}
                </span>
              )}
            </div>
          </div>
          <div className="flex shrink-0 items-center gap-2 flex-wrap">
            <StatusBadge status={project.status} />
            {(() => {
              const mode = project.config?.research_mode ?? "standard";
              return (
                <span
                  className="rounded px-2 py-0.5 text-[11px] font-semibold uppercase tracking-wider"
                  style={
                    mode === "discovery"
                      ? { background: "var(--tron-accent)", color: "var(--tron-bg)" }
                      : mode === "frontier"
                        ? { background: "color-mix(in srgb, var(--tron-accent) 40%, transparent)", color: "var(--tron-text)" }
                        : { border: "1px solid var(--tron-border)", color: "var(--tron-text-muted)" }
                  }
                  title="Research mode: Evidence Gate and verification rules depend on this."
                >
                  {mode === "discovery" ? "Discovery" : mode === "frontier" ? "Frontier" : "Standard"}
                </span>
              );
            })()}
            {isActive && project.status !== "pending_review" && <StartCycleButton projectId={id} />}
            {project.status === "active" && <CancelRunButton projectId={id} />}
            {project.status === "done" && <CreateFollowupButton projectId={id} />}
            <DeleteProjectButton projectId={id} projectQuestion={project.question} />
          </div>
        </div>

        {/* Metadata grid */}
        <div className="grid grid-cols-2 gap-0 sm:grid-cols-3 lg:grid-cols-6">
          {[
            {
              label: "Phase",
              value: (
                <span className="font-mono text-sm font-semibold uppercase"
                  style={{ color: project.status.startsWith("failed") ? "var(--tron-error, #ef4444)" : "var(--tron-accent)" }}>
                  {project.phase}
                  {project.status.startsWith("failed") && (
                    <span className="ml-1.5 text-[9px] font-bold px-1 py-0.5 rounded"
                      style={{ background: "rgba(239,68,68,0.15)", color: "rgb(248,113,113)" }}>
                      FAILED
                    </span>
                  )}
                </span>
              ),
            },
            {
              label: "Runtime",
              value: (
                <LiveElapsedTimer
                  created_at={project.created_at ?? ""}
                  completed_at={completedAt}
                  isActive={isActive}
                  className="font-mono text-sm font-semibold"
                  style={{ color: "var(--tron-text)" }}
                />
              ),
            },
            {
              label: "Findings",
              value: (
                <span className="font-mono text-sm font-semibold"
                  style={{ color: "var(--tron-text)" }}>
                  {project.findings_count}
                </span>
              ),
            },
            {
              label: "Sources",
              value: (
                <span className="font-mono text-sm font-semibold"
                  style={{ color: "var(--tron-text)" }}>
                  {project.quality_gate?.evidence_gate?.metrics?.unique_source_count ?? "—"}
                </span>
              ),
            },
            {
              label: "Budget",
              value: (
                <span className="font-mono text-sm font-semibold" title={project.spend_breakdown && Object.keys(project.spend_breakdown).length > 0 ? Object.entries(project.spend_breakdown).map(([k, v]) => `${k}: $${v.toFixed(4)}`).join(" | ") : undefined} style={{ color: "var(--tron-text)" }}>
                  ${project.current_spend.toFixed(2)} / ${project.config?.budget_limit ?? 3}
                </span>
              ),
            },
            {
              label: "Verify Rate",
              value: (
                <span className="font-mono text-sm font-semibold"
                  style={{ color: "var(--tron-text)" }}>
                  {Math.round(
                    (project.quality_gate?.evidence_gate?.metrics?.claim_support_rate ?? 0) * 100
                  )}
                  %
                </span>
              ),
            },
          ].map((item, idx, arr) => (
            <div
              key={item.label}
              className="px-5 py-3"
              style={{
                borderRight: idx < arr.length - 1 ? "1px solid var(--tron-border)" : undefined,
                borderTop: "1px solid var(--tron-border)",
              }}
            >
              <div className="metric-label mb-1">{item.label}</div>
              {item.value}
            </div>
          ))}
        </div>

        {/* Started at footer */}
        <div
          className="px-5 py-2 flex items-center gap-4 flex-wrap"
          style={{ borderTop: "1px solid var(--tron-border)", background: "var(--tron-bg)" }}
        >
          <span className="text-[11px] font-mono" style={{ color: "var(--tron-text-dim)" }}>
            Started: <span style={{ color: "var(--tron-text-muted)" }}>{formatDate(project.created_at)}</span>
          </span>
          {project.feedback_count > 0 && (
            <span className="text-[11px] font-mono" style={{ color: "var(--tron-text-dim)" }}>
              Feedback: <span style={{ color: "var(--tron-text-muted)" }}>{project.feedback_count}</span>
            </span>
          )}
          {project.prior_knowledge && (project.prior_knowledge.principles_count > 0 || project.prior_knowledge.findings_count > 0) && (
            <span className="text-[11px] font-mono" style={{ color: "var(--tron-text-dim)" }}>
              Seeded with <span style={{ color: "var(--tron-accent)" }}>{project.prior_knowledge.principles_count}</span> principles and <span style={{ color: "var(--tron-accent)" }}>{project.prior_knowledge.findings_count}</span> findings from past projects
            </span>
          )}
        </div>
      </div>

      {project.status === "pending_review" && (
        <ReviewPanel projectId={id} project={project} audit={audit} />
      )}

      {/* ── Execution Tree ────────────────────────────────────── */}
      <div
        className="rounded-lg px-5 py-4"
        style={{ border: "1px solid var(--tron-border)", background: "var(--tron-bg-panel)" }}
      >
        <div className="mb-3 flex items-center justify-between">
          <span className="text-[11px] font-semibold uppercase tracking-wider" style={{ color: "var(--tron-text-muted)" }}>
            Execution Pipeline
          </span>
          <span className="font-mono text-[10px]" style={{ color: "var(--tron-text-dim)" }}>
            {project.status === "done" ? "COMPLETED" : isActive ? "RUNNING" : project.status.startsWith("failed") ? "FAILED" : "STOPPED"}
          </span>
        </div>
        <ExecutionTree
          currentPhase={project.phase}
          status={project.status}
          phaseTimings={project.phase_timings}
          experimentSummary={project.experiment_summary ?? null}
        />
      </div>

      {/* ── Council Room (If this is a parent project with follow-ups) ─── */}
      {(followUpIds.length > 0 || project.has_master_dossier || project.council_status) && (
        <CouncilRoom 
          projectId={id} 
          councilStatus={project.council_status} 
          hasMasterDossier={!!project.has_master_dossier} 
        />
      )}

      {/* ── Gate Metrics (inline, lightweight) ───────────────── */}
      <GateMetricsInline project={project} calibratedThresholds={calibratedThresholds ?? undefined} />

      {/* ── Research Intelligence (Connect, Verify, Governor) ─── */}
      <ResearchIntelligencePanel project={project} />

      {/* ── Autonomous Experiment (Sandbox / Sub-agents) ───────── */}
      {project.experiment_summary && (
        <div
          className="rounded-lg px-5 py-4"
          style={{ border: "1px solid var(--tron-border)", background: "var(--tron-bg-panel)" }}
        >
          <div className="mb-3 flex items-center justify-between">
            <span className="text-[11px] font-semibold uppercase tracking-wider" style={{ color: "var(--tron-accent)" }}>
              Autonomous Experiment
            </span>
            <span
              className="rounded px-2 py-0.5 font-mono text-[10px] font-bold"
              style={{
                background: project.experiment_summary.success
                  ? "color-mix(in srgb, var(--tron-success) 20%, transparent)"
                  : "color-mix(in srgb, var(--tron-amber, #f59e0b) 20%, transparent)",
                color: project.experiment_summary.success ? "var(--tron-success)" : "var(--tron-amber, #f59e0b)",
                border: "1px solid var(--tron-border)",
              }}
            >
              {project.experiment_summary.success ? "Sandbox OK" : "Sandbox ran (no success)"}
            </span>
          </div>
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-4 text-sm">
            <div>
              <div className="metric-label mb-1">Iterations</div>
              <div className="font-mono font-semibold" style={{ color: "var(--tron-text)" }}>
                {project.experiment_summary.iterations}
              </div>
              <p className="text-[10px] mt-0.5" style={{ color: "var(--tron-text-dim)" }}>
                Code gen + sandbox runs
              </p>
            </div>
            <div>
              <div className="metric-label mb-1">Sub-agents spawned</div>
              <div className="font-mono font-semibold" style={{ color: "var(--tron-text)" }}>
                {project.experiment_summary.subagents_spawned}
              </div>
              <p className="text-[10px] mt-0.5" style={{ color: "var(--tron-text-dim)" }}>
                Their cost is rolled into this project&apos;s budget
              </p>
            </div>
          </div>
          <p className="mt-3 text-[11px]" style={{ color: "var(--tron-text-dim)" }}>
            Trial &amp; Error runs after Synthesize: code is generated, executed in an isolated sandbox, and retried on errors. Sub-agent costs are included in the Budget above.
          </p>
        </div>
      )}

      {/* ── Memory Applied ────────────────────────────────────── */}
      <MemoryAppliedPanel project={project} />

      {/* ── Discovery Insights (discovery mode only) ───────────── */}
      {project.config?.research_mode === "discovery" && project.discovery_analysis?.discovery_brief && (
        <div
          className="rounded-lg px-5 py-4"
          style={{ border: "1px solid var(--tron-border)", background: "var(--tron-bg-panel)" }}
        >
          <div className="mb-3 text-[11px] font-semibold uppercase tracking-wider" style={{ color: "var(--tron-accent)" }}>
            Discovery Insights
          </div>
          <div className="grid gap-4 sm:grid-cols-2">
            {(project.discovery_analysis.discovery_brief.novel_connections?.length ?? 0) > 0 && (
              <div>
                <div className="mb-1 text-[10px] font-semibold uppercase" style={{ color: "var(--tron-text-muted)" }}>Novel connections</div>
                <ul className="list-disc pl-4 text-sm space-y-0.5" style={{ color: "var(--tron-text)" }}>
                  {project.discovery_analysis.discovery_brief.novel_connections!.slice(0, 5).map((nc, i) => (
                    <li key={i}>{nc}</li>
                  ))}
                </ul>
              </div>
            )}
            {(project.discovery_analysis.discovery_brief.emerging_concepts?.length ?? 0) > 0 && (
              <div>
                <div className="mb-1 text-[10px] font-semibold uppercase" style={{ color: "var(--tron-text-muted)" }}>Emerging concepts</div>
                <ul className="list-disc pl-4 text-sm space-y-0.5" style={{ color: "var(--tron-text)" }}>
                  {project.discovery_analysis.discovery_brief.emerging_concepts!.slice(0, 5).map((ec, i) => (
                    <li key={i}>{ec}</li>
                  ))}
                </ul>
              </div>
            )}
            {(project.discovery_analysis.discovery_brief.research_frontier?.length ?? 0) > 0 && (
              <div>
                <div className="mb-1 text-[10px] font-semibold uppercase" style={{ color: "var(--tron-text-muted)" }}>Research frontier</div>
                <ul className="list-disc pl-4 text-sm space-y-0.5" style={{ color: "var(--tron-text)" }}>
                  {project.discovery_analysis.discovery_brief.research_frontier!.slice(0, 5).map((rf, i) => (
                    <li key={i}>{rf}</li>
                  ))}
                </ul>
              </div>
            )}
            {(project.discovery_analysis.discovery_brief.unexplored_opportunities?.length ?? 0) > 0 && (
              <div>
                <div className="mb-1 text-[10px] font-semibold uppercase" style={{ color: "var(--tron-text-muted)" }}>Unexplored opportunities</div>
                <ul className="list-disc pl-4 text-sm space-y-0.5" style={{ color: "var(--tron-text)" }}>
                  {project.discovery_analysis.discovery_brief.unexplored_opportunities!.slice(0, 5).map((uo, i) => (
                    <li key={i}>{uo}</li>
                  ))}
                </ul>
              </div>
            )}
          </div>
          {project.discovery_analysis.discovery_brief.key_hypothesis && (
            <blockquote className="mt-4 pl-4 border-l-2 text-sm" style={{ borderColor: "var(--tron-accent)", color: "var(--tron-text-muted)" }}>
              {project.discovery_analysis.discovery_brief.key_hypothesis}
            </blockquote>
          )}
        </div>
      )}

      {/* ── Activity Feed ─────────────────────────────────────── */}
      <ActivityFeed projectId={id} currentPhase={project.phase} isProjectActive={isActive} />

      {/* ── Tabs (Report, Findings, Sources, History, Audit) ─── */}
      <div
        className="rounded-lg overflow-hidden"
        style={{ border: "1px solid var(--tron-border)", background: "var(--tron-bg-panel)" }}
      >
        <div className="px-5 pt-4">
          <ResearchDetailTabs projectId={id} initialMarkdown={markdown} hasPdf={!!pdfInfo} project={project} />
        </div>
        <div style={{ height: 4 }} />
      </div>
    </div>
  );
}

/* ── Research Intelligence (Connect, Verify, Governor) ─────────── */
function ResearchIntelligencePanel({ project }: { project: ResearchProjectDetail }) {
  const hasGovernor = !!project.governor_lane;
  const hasThesis = !!project.thesis?.current;
  const hasContra = (project.contradictions?.contradictions?.length ?? 0) > 0;
  const hasFactCheck = (project.fact_check_summary?.total ?? 0) > 0;
  const hasLedger = (project.claim_ledger_summary?.total ?? 0) > 0;
  if (!hasGovernor && !hasThesis && !hasContra && !hasFactCheck && !hasLedger) return null;

  return (
    <div
      className="rounded-lg px-5 py-4"
      style={{ border: "1px solid var(--tron-border)", background: "var(--tron-bg-panel)" }}
    >
      <div className="mb-3 text-[11px] font-semibold uppercase tracking-wider" style={{ color: "var(--tron-accent)" }}>
        Research Intelligence
      </div>
      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        {hasGovernor && (
          <div>
            <div className="mb-1 text-[10px] font-semibold uppercase" style={{ color: "var(--tron-text-muted)" }}>Token Governor</div>
            <span
              className="inline-block rounded px-2 py-0.5 font-mono text-xs font-bold capitalize"
              style={{
                background:
                  project.governor_lane === "strong"
                    ? "color-mix(in srgb, var(--tron-accent) 25%, transparent)"
                    : project.governor_lane === "mid"
                      ? "color-mix(in srgb, var(--tron-accent) 12%, transparent)"
                      : "var(--tron-bg)",
                color: "var(--tron-text)",
                border: "1px solid var(--tron-border)",
              }}
            >
              {project.governor_lane}
            </span>
            <p className="mt-0.5 text-[10px]" style={{ color: "var(--tron-text-dim)" }}>
              Lane used for Verify / Synthesize / Critic
            </p>
          </div>
        )}
        {hasThesis && (
          <div className="sm:col-span-2">
            <div className="mb-1 text-[10px] font-semibold uppercase" style={{ color: "var(--tron-text-muted)" }}>Thesis (Connect)</div>
            <p className="text-sm leading-snug" style={{ color: "var(--tron-text)" }}>
              {(project.thesis!.current ?? "").slice(0, 280)}
              {(project.thesis!.current?.length ?? 0) > 280 ? "…" : ""}
            </p>
            {typeof project.thesis!.confidence === "number" && (
              <span className="text-[10px] font-mono" style={{ color: "var(--tron-text-dim)" }}>
                Confidence: {Math.round(project.thesis!.confidence * 100)}%
              </span>
            )}
          </div>
        )}
        {hasContra && (
          <div className="sm:col-span-2">
            <div className="mb-1 text-[10px] font-semibold uppercase" style={{ color: "var(--tron-text-muted)" }}>Contradictions</div>
            <p className="text-sm font-mono" style={{ color: "var(--tron-text)" }}>
              {project.contradictions!.contradictions!.length} source disagreement(s)
            </p>
            <ul className="mt-1 space-y-1 text-xs" style={{ color: "var(--tron-text-dim)" }}>
              {project.contradictions!.contradictions!.slice(0, 3).map((c, i) => {
                const t = (c.summary || c.claim || "Conflict") ?? "";
                return (
                  <li key={i}>
                    {t.slice(0, 80)}
                    {t.length > 80 ? "…" : ""}
                  </li>
                );
              })}
            </ul>
          </div>
        )}
        {hasFactCheck && (
          <div>
            <div className="mb-1 text-[10px] font-semibold uppercase" style={{ color: "var(--tron-text-muted)" }}>Fact-Check</div>
            <div className="flex flex-wrap gap-1.5">
              <span className="rounded px-1.5 py-0.5 font-mono text-[10px]" style={{ background: "color-mix(in srgb, var(--tron-success) 15%, transparent)", color: "var(--tron-text)" }}>
                ✓ {project.fact_check_summary!.confirmed}
              </span>
              <span className="rounded px-1.5 py-0.5 font-mono text-[10px]" style={{ background: "color-mix(in srgb, var(--tron-error) 15%, transparent)", color: "var(--tron-text)" }}>
                ✗ {project.fact_check_summary!.disputed}
              </span>
              <span className="rounded px-1.5 py-0.5 font-mono text-[10px]" style={{ background: "var(--tron-bg)", color: "var(--tron-text-dim)" }}>
                ? {project.fact_check_summary!.unverifiable}
              </span>
            </div>
            <p className="mt-0.5 text-[10px]" style={{ color: "var(--tron-text-dim)" }}>
              {project.fact_check_summary!.total} facts checked
            </p>
          </div>
        )}
        {hasLedger && (
          <div>
            <div className="mb-1 text-[10px] font-semibold uppercase" style={{ color: "var(--tron-text-muted)" }}>Claim Ledger</div>
            <div className="flex flex-wrap gap-1.5">
              <span className="rounded px-1.5 py-0.5 font-mono text-[10px]" style={{ background: "color-mix(in srgb, var(--tron-success) 15%, transparent)", color: "var(--tron-text)" }}>
                Verified {project.claim_ledger_summary!.verified}
              </span>
              <span className="rounded px-1.5 py-0.5 font-mono text-[10px]" style={{ background: "color-mix(in srgb, var(--tron-accent) 15%, transparent)", color: "var(--tron-text)" }}>
                Auth. {project.claim_ledger_summary!.authoritative}
              </span>
              <span className="rounded px-1.5 py-0.5 font-mono text-[10px]" style={{ color: "var(--tron-text-dim)" }}>
                Unver. {project.claim_ledger_summary!.unverified}
              </span>
              {(project.claim_ledger_summary!.in_contradiction ?? 0) > 0 && (
                <span className="rounded px-1.5 py-0.5 font-mono text-[10px]" style={{ background: "color-mix(in srgb, var(--tron-amber, #f59e0b) 15%, transparent)", color: "var(--tron-text)" }}>
                  Contr. {project.claim_ledger_summary!.in_contradiction}
                </span>
              )}
            </div>
            <p className="mt-0.5 text-[10px]" style={{ color: "var(--tron-text-dim)" }}>
              {project.claim_ledger_summary!.total} claims · see Audit tab
            </p>
          </div>
        )}
      </div>
    </div>
  );
}

/* ── Inline Gate Metrics ─────────────────────────────────────── */
function GateMetricsInline({
  project,
  calibratedThresholds,
}: {
  project: ResearchProjectDetail;
  calibratedThresholds?: CalibratedThresholds | null;
}) {
  const gate = project.quality_gate?.evidence_gate;
  const metrics = gate?.metrics;

  if (!metrics) {
    return (
      <div className="rounded-lg px-5 py-4"
        style={{ border: "1px solid var(--tron-border)", background: "var(--tron-bg-panel)" }}>
        <span className="text-[11px] font-semibold uppercase tracking-wider" style={{ color: "var(--tron-text-muted)" }}>
          Gate Metrics
        </span>
        <p className="mt-2 text-sm" style={{ color: "var(--tron-text-dim)" }}>
          Quality gate data not yet available. Run the Verify phase first.
        </p>
      </div>
    );
  }

  const gateStatus = gate.status || (gate as { decision?: string }).decision || "pending";
  const minSources = calibratedThresholds?.unique_source_count_min ?? 5;
  const minFindings = calibratedThresholds?.findings_count_min ?? 8;
  const minVerified = calibratedThresholds?.verified_claim_count_min ?? 2;
  const items = [
    { label: "Sources Found", value: metrics.unique_source_count, minRequired: minSources },
    { label: "Findings", value: metrics.findings_count, minRequired: minFindings },
    { label: "Verified Claims", value: metrics.verified_claim_count, minRequired: minVerified },
    { label: "Support Rate", value: `${Math.round(metrics.claim_support_rate * 100)}%`, minRequired: null as number | null },
    { label: "Source Reliability", value: `${Math.round(metrics.high_reliability_source_ratio * 100)}%`, minRequired: null as number | null },
    { label: "Read Success (Explore + Focus)", value: `${metrics.read_successes}/${metrics.read_attempts}`, minRequired: null as number | null },
  ];

  return (
    <div className="rounded-lg"
      style={{
        border: `1px solid ${
          gateStatus === "passed"
            ? "color-mix(in srgb, var(--tron-success) 30%, transparent)"
            : gateStatus === "failed"
            ? "color-mix(in srgb, var(--tron-error) 30%, transparent)"
            : gateStatus === "pending_review"
            ? "color-mix(in srgb, var(--tron-amber, #f59e0b) 30%, transparent)"
            : "var(--tron-border)"
        }`,
        background: "var(--tron-bg-panel)",
      }}>
      <div className="flex items-center gap-2 px-5 py-2.5"
        style={{ borderBottom: "1px solid var(--tron-border)" }}>
        <span className="text-[11px] font-semibold uppercase tracking-wider" style={{ color: "var(--tron-text-muted)" }}>
          Evidence Gate
        </span>
        <span
          className="rounded px-1.5 py-0.5 font-mono text-[10px] font-bold"
          style={{
            background:
              gateStatus === "passed"
                ? "color-mix(in srgb, var(--tron-success) 10%, transparent)"
                : gateStatus === "failed"
                ? "color-mix(in srgb, var(--tron-error) 10%, transparent)"
                : gateStatus === "pending_review"
                ? "color-mix(in srgb, var(--tron-amber, #f59e0b) 10%, transparent)"
                : "var(--tron-bg)",
            color:
              gateStatus === "passed"
                ? "var(--tron-success)"
                : gateStatus === "failed"
                ? "var(--tron-error)"
                : gateStatus === "pending_review"
                ? "var(--tron-amber, #f59e0b)"
                : "var(--tron-text-dim)",
            border: `1px solid ${
              gateStatus === "passed"
                ? "color-mix(in srgb, var(--tron-success) 25%, transparent)"
                : gateStatus === "failed"
                ? "color-mix(in srgb, var(--tron-error) 25%, transparent)"
                : gateStatus === "pending_review"
                ? "color-mix(in srgb, var(--tron-amber, #f59e0b) 25%, transparent)"
                : "var(--tron-border)"
            }`,
          }}>
          {gateStatus.toUpperCase()}
        </span>
        {gate.reasons && gate.reasons.length > 0 && (
          <span className="text-[10px] font-mono" style={{ color: "var(--tron-text-dim)" }}>
            — {gate.reasons[0]}
          </span>
        )}
      </div>
      <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-6">
        {items.map((m, idx, arr) => (
          <div key={m.label} className="px-4 py-3"
            style={{ borderRight: idx < arr.length - 1 ? "1px solid var(--tron-border)" : undefined }}>
            <div className="metric-label mb-1">{m.label}</div>
            <div className="font-mono text-sm font-bold" style={{ color: "var(--tron-text)" }}>
              {m.value}
              {m.minRequired != null && (
                <span className="ml-1 font-normal text-tron-dim">/ min {m.minRequired}</span>
              )}
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}

function MemoryAppliedPanel({ project }: { project: ResearchProjectDetail }) {
  const memory = project.memory_applied;
  const selected = memory?.selected_strategy;
  const mode = memory?.mode ?? "v2_disabled";
  if (!memory) {
    return null;
  }
  const confidence =
    typeof selected?.selection_confidence === "number"
      ? selected.selection_confidence
      : typeof selected?.confidence === "number"
        ? selected.confidence
        : 0;
  const confidencePct = Math.max(0, Math.min(100, Math.round(confidence * 100)));
  const policy = selected?.policy || {};
  const preferredTypes = Object.entries(policy.preferred_query_types || {});
  const domainOverrides = policy.domain_rank_overrides || {};
  const modeColor =
    mode === "v2_applied"
      ? "var(--tron-success)"
      : mode === "v2_fallback"
      ? "var(--tron-amber, #f59e0b)"
      : "var(--tron-text-dim)";
  return (
    <div
      className="rounded-lg"
      style={{ border: "1px solid var(--tron-border)", background: "var(--tron-bg-panel)" }}
    >
      <div className="flex items-center gap-2 px-5 py-2.5" style={{ borderBottom: "1px solid var(--tron-border)" }}>
        <span className="text-[11px] font-semibold uppercase tracking-wider" style={{ color: "var(--tron-text-muted)" }}>
          Memory Applied
        </span>
        <span className="rounded px-1.5 py-0.5 font-mono text-[10px] font-bold"
          style={{ border: "1px solid var(--tron-border)", color: "var(--tron-accent)" }}>
          {selected?.name || "Strategy"}
        </span>
        <span className="rounded px-1.5 py-0.5 font-mono text-[10px] font-bold"
          style={{ border: "1px solid var(--tron-border)", color: modeColor }}>
          {mode.toUpperCase()}
        </span>
      </div>
      <div className="grid grid-cols-1 md:grid-cols-3 gap-0">
        <div className="px-5 py-3" style={{ borderRight: "1px solid var(--tron-border)" }}>
          <div className="metric-label mb-1">Strategy Confidence</div>
          <div className="font-mono text-sm font-semibold" style={{ color: "var(--tron-text)" }}>
            {selected?.id ? `${confidencePct}%` : "—"}
          </div>
          <div className="mt-2 h-1.5 rounded" style={{ background: "var(--tron-bg)" }}>
            <div
              className="h-1.5 rounded"
              style={{ width: `${selected?.id ? confidencePct : 0}%`, background: modeColor }}
            />
          </div>
          <div className="mt-2 text-[11px]" style={{ color: "var(--tron-text-dim)" }}>
            Expected benefit: {memory?.expected_benefit || "better pass-rate on similar runs"}
          </div>
          {memory?.fallback_reason && (
            <div className="mt-1 text-[11px]" style={{ color: "var(--tron-text-dim)" }}>
              Fallback reason: {memory.fallback_reason}
            </div>
          )}
        </div>
        <div className="px-5 py-3" style={{ borderRight: "1px solid var(--tron-border)" }}>
          <div className="metric-label mb-1">Active Rules</div>
          <div className="text-[11px] font-mono" style={{ color: "var(--tron-text)" }}>
            relevance {policy.relevance_threshold ?? "—"} | critic {policy.critic_threshold ?? "—"} | revise {policy.revise_rounds ?? "—"}
          </div>
          <div className="mt-2 text-[11px]" style={{ color: "var(--tron-text-dim)" }}>
            Similar episodes: {memory?.similar_episode_count ?? memory?.confidence_drivers?.similar_episode_count ?? 0}
          </div>
          {preferredTypes.length > 0 && (
            <div className="mt-2 text-[11px]" style={{ color: "var(--tron-text-dim)" }}>
              Query mix: {preferredTypes.map(([k, v]) => `${k}:${v}`).join(" · ")}
            </div>
          )}
          {memory?.confidence_drivers && (
            <div className="mt-2 text-[11px]" style={{ color: "var(--tron-text-dim)" }}>
              Why: score {memory.confidence_drivers.strategy_score ?? "—"} · overlap {memory.confidence_drivers.query_overlap ?? "—"} · recency {memory.confidence_drivers.similar_recency_weight ?? "—"}
            </div>
          )}
        </div>
        <div className="px-5 py-3">
          <div className="metric-label mb-1">Preferred Domains</div>
          <PreferredDomainsTabs domainOverrides={domainOverrides} />
        </div>
      </div>
    </div>
  );
}
