import Link from "next/link";
import { notFound } from "next/navigation";
import {
  getResearchProject,
  getLatestReportMarkdown,
  type ResearchProjectDetail,
} from "@/lib/operator/research";
import { StatusBadge } from "@/components/StatusBadge";
import { StartCycleButton } from "@/components/StartCycleButton";
import { CreateFollowupButton } from "@/components/CreateFollowupButton";
import { DeleteProjectButton } from "@/components/DeleteProjectButton";
import { ExecutionTree } from "@/components/ExecutionTree";
import { ResearchDetailTabs } from "./ResearchDetailTabs";

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

function elapsed(from: string, to?: string): string {
  if (!from) return "—";
  try {
    const start = new Date(from).getTime();
    const end = to ? new Date(to).getTime() : Date.now();
    const ms = end - start;
    if (ms < 60_000) return `${Math.round(ms / 1000)}s`;
    if (ms < 3_600_000) return `${Math.round(ms / 60_000)}m`;
    return `${(ms / 3_600_000).toFixed(1)}h`;
  } catch {
    return "—";
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

  const markdown = await getLatestReportMarkdown(id);
  const isActive = project.status !== "done" && project.status !== "failed";

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
          <div className="min-w-0 flex-1">
            <h1 className="text-lg font-semibold leading-snug" style={{ color: "var(--tron-text)" }}>
              {project.question || "Untitled Research"}
            </h1>
            <div className="mt-1 flex items-center gap-2">
              <span className="font-mono text-[11px]" style={{ color: "var(--tron-text-dim)" }}>
                {id}
              </span>
            </div>
          </div>
          <div className="flex shrink-0 items-center gap-2">
            <StatusBadge status={project.status} />
            {isActive && <StartCycleButton projectId={id} />}
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
                  style={{ color: "var(--tron-accent)" }}>
                  {project.phase}
                </span>
              ),
            },
            {
              label: "Runtime",
              value: (
                <span className="font-mono text-sm font-semibold"
                  style={{ color: "var(--tron-text)" }}>
                  {elapsed(project.created_at)}
                </span>
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
                <span className="font-mono text-sm font-semibold"
                  style={{ color: "var(--tron-text)" }}>
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
          className="px-5 py-2 flex items-center gap-4"
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
        </div>
      </div>

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
            {project.status === "done" ? "COMPLETED" : isActive ? "RUNNING" : "STOPPED"}
          </span>
        </div>
        <ExecutionTree
          currentPhase={project.phase}
          status={project.status}
          phaseTimings={project.phase_timings}
        />
      </div>

      {/* ── Gate Metrics (inline, lightweight) ───────────────── */}
      <GateMetricsInline project={project} />

      {/* ── Tabs (Report, Findings, Sources, History, Audit) ─── */}
      <div
        className="rounded-lg overflow-hidden"
        style={{ border: "1px solid var(--tron-border)", background: "var(--tron-bg-panel)" }}
      >
        <div className="px-5 pt-4">
          <ResearchDetailTabs projectId={id} initialMarkdown={markdown} />
        </div>
        <div style={{ height: 4 }} />
      </div>
    </div>
  );
}

/* ── Inline Gate Metrics ─────────────────────────────────────── */
function GateMetricsInline({ project }: { project: ResearchProjectDetail }) {
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

  const gateStatus = gate.status || "pending";
  const items = [
    { label: "Sources Found", value: metrics.unique_source_count, threshold: 5 },
    { label: "Findings", value: metrics.findings_count, threshold: 8 },
    { label: "Verified Claims", value: metrics.verified_claim_count, threshold: 2 },
    { label: "Support Rate", value: `${Math.round(metrics.claim_support_rate * 100)}%`, threshold: null },
    { label: "Source Reliability", value: `${Math.round(metrics.high_reliability_source_ratio * 100)}%`, threshold: null },
    { label: "Read Success", value: `${metrics.read_successes}/${metrics.read_attempts}`, threshold: null },
  ];

  return (
    <div className="rounded-lg"
      style={{
        border: `1px solid ${
          gateStatus === "passed"
            ? "color-mix(in srgb, var(--tron-success) 30%, transparent)"
            : gateStatus === "failed"
            ? "color-mix(in srgb, var(--tron-error) 30%, transparent)"
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
                : "var(--tron-bg)",
            color:
              gateStatus === "passed"
                ? "var(--tron-success)"
                : gateStatus === "failed"
                ? "var(--tron-error)"
                : "var(--tron-text-dim)",
            border: `1px solid ${
              gateStatus === "passed"
                ? "color-mix(in srgb, var(--tron-success) 25%, transparent)"
                : gateStatus === "failed"
                ? "color-mix(in srgb, var(--tron-error) 25%, transparent)"
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
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
