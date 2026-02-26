import Link from "next/link";
import { getHealth } from "@/lib/operator/health";
import { listJobs } from "@/lib/operator/jobs";
import { listResearchProjects } from "@/lib/operator/research";
import { DashboardQuickActions } from "@/components/DashboardQuickActions";
import { EventFeed } from "@/components/EventFeed";
import { LiveRefresh } from "@/components/LiveRefresh";
import { StatusBadge } from "@/components/StatusBadge";

export const dynamic = "force-dynamic";

const PHASE_ORDER = ["explore", "focus", "connect", "verify", "synthesize"];
function phaseProgress(phase: string): number {
  const i = PHASE_ORDER.indexOf(phase.toLowerCase());
  if (i < 0) return 0;
  return ((i + 1) / PHASE_ORDER.length) * 100;
}

export default async function CommandCenterPage() {
  const [health, projects, runningJobsResult] = await Promise.all([
    getHealth(),
    listResearchProjects(),
    listJobs(500, 0, "RUNNING"),
  ]);
  const healthy = health.healthy ?? false;
  const failures = health.recent_failures ?? [];
  const runningJobsCount = runningJobsResult.jobs.length;
  const activeProjects = projects.filter(
    (p) => p.status !== "done" && p.status !== "failed"
  );
  const doneProjects = projects.filter((p) => p.status === "done");
  const failedProjects = projects.filter((p) => p.status === "failed");
  const totalSpend = projects.reduce((sum, p) => sum + (p.current_spend ?? 0), 0);

  const verifyRates = projects
    .filter((p) => p.status === "done")
    .map((p) => {
      const metrics =
        (
          p as unknown as {
            quality_gate?: { evidence_gate?: { metrics?: { claim_support_rate?: number } } };
          }
        ).quality_gate?.evidence_gate?.metrics;
      return typeof metrics?.claim_support_rate === "number"
        ? metrics.claim_support_rate
        : null;
    })
    .filter((rate): rate is number => rate !== null);
  const avgVerifyRate =
    verifyRates.length > 0
      ? `${Math.round((verifyRates.reduce((sum, rate) => sum + rate, 0) / verifyRates.length) * 100)}%`
      : "—";

  const blockedReadsValues = projects
    .map((p) => {
      const metrics =
        (
          p as unknown as {
            quality_gate?: { evidence_gate?: { metrics?: { read_failures?: number } } };
          }
        ).quality_gate?.evidence_gate?.metrics;
      return typeof metrics?.read_failures === "number" ? metrics.read_failures : null;
    })
    .filter((value): value is number => value !== null);
  const blockedReads =
    blockedReadsValues.length > 0
      ? String(blockedReadsValues.reduce((sum, value) => sum + value, 0))
      : "—";

  const needsLiveRefresh = runningJobsCount > 0 || activeProjects.length > 0;

  return (
    <div className="space-y-6 animate-fade-in">
      {/* ── Page header ──────────────────────────────────────── */}
      <div className="flex flex-wrap items-center justify-between gap-4">
        <div className="flex items-center gap-3">
          <h1 className="text-xl font-semibold tracking-tight" style={{ color: "var(--tron-text)" }}>
            Command Center
          </h1>
          <LiveRefresh enabled={needsLiveRefresh} intervalMs={6000} showIndicator={true} />
          <p className="mt-0.5 text-sm" style={{ color: "var(--tron-text-muted)" }}>
            System overview — running jobs, API status, active research
          </p>
        </div>
        <Link
          href="/research"
          className="flex h-9 items-center rounded px-4 text-sm font-medium text-white transition-opacity hover:opacity-90"
          style={{ background: "var(--tron-accent)" }}
        >
          + New Project
        </Link>
      </div>

      {/* ── System Status Bar ─────────────────────────────────── */}
      <div
        className="flex flex-wrap items-center gap-4 rounded-lg px-4 py-3 text-[12px]"
        style={{
          background: "var(--tron-bg-panel)",
          border: `1px solid ${healthy ? "var(--tron-border)" : "rgba(244,63,94,0.35)"}`,
        }}
      >
        <div className="flex items-center gap-2">
          <span
            className="inline-block h-2 w-2 rounded-full"
            style={{ background: healthy ? "var(--tron-success)" : "var(--tron-error)" }}
          />
          <span
            className="font-semibold"
            style={{ color: healthy ? "var(--tron-success)" : "var(--tron-error)" }}
          >
            {healthy ? "System Healthy" : "System Alert"}
          </span>
        </div>

        <div className="h-4 w-px" style={{ background: "var(--tron-border)" }} />

        {health.disk_used_pct != null && (
          <div className="flex items-center gap-1.5">
            <span className="metric-label">Disk</span>
            <span
              className="font-mono font-semibold"
              style={{ color: health.disk_used_pct > 85 ? "var(--tron-error)" : "var(--tron-text)" }}
            >
              {health.disk_used_pct}%
            </span>
          </div>
        )}

        {health.load_1m != null && (
          <div className="flex items-center gap-1.5">
            <span className="metric-label">Load</span>
            <span className="font-mono font-semibold" style={{ color: "var(--tron-text)" }}>
              {health.load_1m}
            </span>
          </div>
        )}

        {health.jobs_failed != null && health.jobs_failed > 0 && (
          <>
            <div className="h-4 w-px" style={{ background: "var(--tron-border)" }} />
            <Link
              href="/jobs?status=FAILED"
              className="flex items-center gap-1.5 font-semibold transition-opacity hover:opacity-80"
              style={{ color: "var(--tron-error)" }}
            >
              {health.jobs_failed} failed job{health.jobs_failed !== 1 ? "s" : ""}
            </Link>
          </>
        )}

        <div className="ml-auto font-mono text-[10px]" style={{ color: "var(--tron-text-dim)" }}>
          {new Date().toUTCString().slice(0, 25)}
        </div>
      </div>

      {/* Failure details */}
      {failures.length > 0 && (
        <div
          className="rounded-lg px-4 py-3"
          style={{
            background: "rgba(244,63,94,0.05)",
            border: "1px solid rgba(244,63,94,0.25)",
          }}
        >
          <p className="text-[12px] font-semibold" style={{ color: "var(--tron-error)" }}>
            Recent Failures
          </p>
          <ul className="mt-2 space-y-1">
            {failures.slice(0, 3).map((f, i) => (
              <li key={i} className="flex items-center gap-2 text-[11px]">
                <span className="font-mono" style={{ color: "var(--tron-text-dim)" }}>—</span>
                <span style={{ color: "var(--tron-text-muted)" }}>{f}</span>
              </li>
            ))}
          </ul>
          <Link
            href="/jobs?status=FAILED"
            className="mt-2 inline-flex items-center gap-1 text-[11px] font-medium transition-opacity hover:opacity-80"
            style={{ color: "var(--tron-error)" }}
          >
            View failed jobs →
          </Link>
        </div>
      )}

      {/* ── Stats row ─────────────────────────────────────────── */}
      <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-6">
        {[
          { label: "Running Jobs",     value: runningJobsCount,      color: "var(--tron-accent)", href: "/jobs?status=RUNNING" },
          { label: "Completed",        value: doneProjects.length,   color: "var(--tron-success)", href: "/research" },
          { label: "Failed",           value: failedProjects.length, color: failedProjects.length > 0 ? "var(--tron-error)" : "var(--tron-text-dim)", href: "/research" },
          { label: "Total Spend",      value: `$${totalSpend.toFixed(2)}`, color: "var(--tron-text)", href: "/research" },
          { label: "Avg Verify Rate",  value: avgVerifyRate,         color: "var(--tron-text)",   href: "/research" },
          { label: "Blocked Reads",    value: blockedReads,          color: blockedReads === "—" ? "var(--tron-text-dim)" : "var(--tron-error)", href: "/research" },
        ].map((s) => (
          <Link
            key={s.label}
            href={s.href}
            className="stat-card block transition-colors hover:border-tron-accent"
          >
            <div className="metric-label">{s.label}</div>
            <div className="mt-1 font-mono text-2xl font-bold" style={{ color: s.color }}>
              {s.value}
            </div>
          </Link>
        ))}
      </div>

      {/* Attention Queue */}
      {(() => {
        const needsAttention = projects.filter((p) => {
          if (p.status.startsWith("failed")) return true;
          if (p.status === "paused_rate_limited") return true;
          if (p.status === "FAILED_BUDGET_EXCEEDED") return true;
          return false;
        });
        if (needsAttention.length === 0) return null;
        return (
          <div
            className="rounded-lg overflow-hidden"
            style={{
              border: "1px solid color-mix(in srgb, var(--tron-error) 25%, transparent)",
              background: "color-mix(in srgb, var(--tron-error) 4%, var(--tron-bg-panel))",
            }}
          >
            <div
              className="flex items-center gap-2 px-4 py-2.5"
              style={{
                borderBottom: "1px solid color-mix(in srgb, var(--tron-error) 15%, transparent)",
              }}
            >
              <span
                className="h-2 w-2 rounded-full animate-pulse"
                style={{ background: "var(--tron-error)" }}
              />
              <span
                className="text-[11px] font-semibold uppercase tracking-wider"
                style={{ color: "var(--tron-error)" }}
              >
                Needs Attention — {needsAttention.length} project
                {needsAttention.length !== 1 ? "s" : ""}
              </span>
            </div>
            <div
              className="divide-y"
              style={{ borderColor: "color-mix(in srgb, var(--tron-error) 12%, transparent)" }}
            >
              {needsAttention.slice(0, 5).map((p) => (
                <Link
                  key={p.id}
                  href={`/research/${p.id}`}
                  className="interactive-row flex items-center gap-3 px-4 py-2.5"
                >
                  <div className="min-w-0 flex-1">
                    <p
                      className="truncate text-[13px] font-medium"
                      style={{ color: "var(--tron-text)" }}
                    >
                      {p.question || p.id}
                    </p>
                    <span
                      className="font-mono text-[10px]"
                      style={{ color: "var(--tron-text-dim)" }}
                    >
                      {p.id}
                    </span>
                  </div>
                  <StatusBadge status={p.status} />
                </Link>
              ))}
            </div>
          </div>
        );
      })()}

      {/* ── Active Projects + Event Feed ──────────────────────── */}
      <div className="grid gap-4 lg:grid-cols-2">
        {/* Active projects */}
        <div
          className="rounded-lg overflow-hidden"
          style={{ border: "1px solid var(--tron-border)", background: "var(--tron-bg-panel)" }}
        >
          <div
            className="flex items-center justify-between px-4 py-3"
            style={{ borderBottom: "1px solid var(--tron-border)" }}
          >
            <span className="text-[11px] font-semibold uppercase tracking-wider" style={{ color: "var(--tron-text-muted)" }}>
              Active Research
            </span>
            <Link
              href="/research"
              className="text-[11px] transition-colors hover:text-tron-accent"
              style={{ color: "var(--tron-text-dim)" }}
            >
              View all →
            </Link>
          </div>

          {activeProjects.length === 0 ? (
            <div className="px-4 py-8 text-center">
              <p className="text-sm" style={{ color: "var(--tron-text-muted)" }}>No active projects.</p>
              <Link href="/research" className="mt-1 block text-[12px] hover:underline" style={{ color: "var(--tron-accent)" }}>
                Start new project →
              </Link>
            </div>
          ) : (
            <div className="divide-y" style={{ borderColor: "var(--tron-border)" }}>
              {activeProjects.slice(0, 6).map((p) => (
                <Link
                  key={p.id}
                  href={`/research/${p.id}`}
                  className="interactive-row flex items-center gap-3 px-4 py-3"
                >
                  <div className="min-w-0 flex-1">
                    <p className="truncate text-[13px] font-medium" style={{ color: "var(--tron-text)" }}>
                      {p.question || p.id}
                    </p>
                    <div className="mt-0.5 flex items-center gap-2">
                      <span className="font-mono text-[10px]" style={{ color: "var(--tron-text-dim)" }}>
                        {p.id}
                      </span>
                      <span style={{ color: "var(--tron-text-dim)" }}>·</span>
                      <span className="text-[10px]" style={{ color: "var(--tron-text-dim)" }}>
                        {p.findings_count} findings
                      </span>
                    </div>
                  </div>
                  <div className="flex flex-col items-end gap-1.5 shrink-0">
                    <StatusBadge status={p.status} />
                    <div className="h-1 w-24 overflow-hidden rounded-full" style={{ background: "var(--tron-border)" }}>
                      <div
                        className="h-full rounded-full transition-all"
                        style={{
                          width: `${phaseProgress(p.phase)}%`,
                          background: "var(--tron-accent)",
                        }}
                      />
                    </div>
                  </div>
                </Link>
              ))}
            </div>
          )}
        </div>

        {/* Event feed */}
        <div
          className="rounded-lg overflow-hidden"
          style={{ border: "1px solid var(--tron-border)", background: "var(--tron-bg-panel)" }}
        >
          <div
            className="flex items-center gap-2 px-4 py-3"
            style={{ borderBottom: "1px solid var(--tron-border)" }}
          >
            <span className="h-1.5 w-1.5 rounded-full animate-pulse" style={{ background: "var(--tron-accent)" }} />
            <span className="text-[11px] font-semibold uppercase tracking-wider" style={{ color: "var(--tron-text-muted)" }}>
              Live Event Feed
            </span>
          </div>
          <div className="px-4 py-3">
            <EventFeed />
          </div>
        </div>
      </div>

      {/* ── Quick Actions ─────────────────────────────────────── */}
      <div
        className="rounded-lg"
        style={{ border: "1px solid var(--tron-border)", background: "var(--tron-bg-panel)" }}
      >
        <div className="px-4 py-3" style={{ borderBottom: "1px solid var(--tron-border)" }}>
          <span className="text-[11px] font-semibold uppercase tracking-wider" style={{ color: "var(--tron-text-muted)" }}>
            Quick Actions
          </span>
          <p className="mt-0.5 text-[12px]" style={{ color: "var(--tron-text-dim)" }}>
            <strong style={{ color: "var(--tron-text-muted)" }}>Factory</strong> runs Discover → Pack → Deliver.{" "}
            <strong style={{ color: "var(--tron-text-muted)" }}>Brain</strong> autonomously selects and executes the next step.
          </p>
        </div>
        <div className="px-4 py-3">
          <DashboardQuickActions />
        </div>
      </div>

      {/* ── Secondary links ───────────────────────────────────── */}
      <div className="flex flex-wrap gap-2">
        {[
          { href: "/jobs",   label: "Audit Logs" },
          { href: "/packs",  label: "Playbooks" },
          { href: "/memory", label: "Memory & Graph" },
        ].map((l) => (
          <Link
            key={l.href}
            href={l.href}
            className="hover-accent flex h-8 items-center rounded px-3 text-[12px] font-medium"
            style={{
              border: "1px solid var(--tron-border)",
              color: "var(--tron-text-muted)",
              background: "transparent",
            }}
          >
            {l.label}
          </Link>
        ))}
      </div>
    </div>
  );
}
