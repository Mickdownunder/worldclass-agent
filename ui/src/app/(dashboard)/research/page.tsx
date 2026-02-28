import Link from "next/link";
import { listResearchProjects } from "@/lib/operator/research";
import { EmptyState } from "@/components/EmptyState";
import { CreateProjectForm } from "@/components/CreateProjectForm";
import { LiveRefresh } from "@/components/LiveRefresh";
import { StatusBadge } from "@/components/StatusBadge";
import { ProjectRowProgress } from "@/components/ProjectRowProgress";

export const dynamic = "force-dynamic";

const PHASE_ORDER = ["explore", "focus", "connect", "verify", "synthesize"];
function phaseProgress(phase: string): number {
  if (phase.toLowerCase() === "done") return 100;
  const i = PHASE_ORDER.indexOf(phase.toLowerCase());
  if (i < 0) return 0;
  return Math.round(((i + 1) / PHASE_ORDER.length) * 100);
}

function formatDate(iso: string): string {
  if (!iso) return "—";
  try {
    return new Intl.DateTimeFormat("en-US", {
      month: "short", day: "numeric", year: "numeric",
    }).format(new Date(iso));
  } catch {
    return iso;
  }
}

export default async function ResearchPage() {
  const projects = await listResearchProjects();

  const active  = projects.filter(
    (p) =>
      p.status !== "done" &&
      p.status !== "failed" &&
      p.status !== "cancelled" &&
      !(typeof p.status === "string" && p.status.startsWith("failed_"))
  );
  const done    = projects.filter((p) => p.status === "done");
  const failed  = projects.filter((p) => p.status === "failed");

  return (
    <div className="space-y-6 animate-fade-in">
      {/* ── Header ────────────────────────────────────────────── */}
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div className="flex items-center gap-3">
          <h1 className="text-xl font-semibold tracking-tight" style={{ color: "var(--tron-text)" }}>
            Research Projects
          </h1>
          <LiveRefresh enabled={active.length > 0} intervalMs={7000} showIndicator={true} />
          <p className="mt-0.5 text-sm" style={{ color: "var(--tron-text-muted)" }}>
            Due-diligence and research jobs — click any row for forensic detail view
          </p>
        </div>
        {/* Summary stats */}
        <div className="flex items-center gap-3 text-[12px]">
          <div className="flex items-center gap-1.5">
            <span className="h-1.5 w-1.5 rounded-full animate-pulse" style={{ background: "var(--tron-accent)" }} />
            <span style={{ color: "var(--tron-text-muted)" }}>{active.length} active</span>
          </div>
          <span style={{ color: "var(--tron-text-dim)" }}>·</span>
          <span style={{ color: "var(--tron-success)" }}>{done.length} done</span>
          <span style={{ color: "var(--tron-text-dim)" }}>·</span>
          <span style={{ color: failed.length > 0 ? "var(--tron-error)" : "var(--tron-text-dim)" }}>
            {failed.length} failed
          </span>
        </div>
      </div>

      {/* ── New Project Form ──────────────────────────────────── */}
      <div
        className="rounded-lg"
        style={{ border: "1px solid var(--tron-border)", background: "var(--tron-bg-panel)" }}
      >
        <div className="px-4 py-3" style={{ borderBottom: "1px solid var(--tron-border)" }}>
          <span className="text-[11px] font-semibold uppercase tracking-wider" style={{ color: "var(--tron-text-muted)" }}>
            New Research Project
          </span>
        </div>
        <div className="px-4 py-4">
          <CreateProjectForm />
        </div>
      </div>

      {/* ── Projects Table ────────────────────────────────────── */}
      {projects.length === 0 ? (
        <EmptyState
          title="No projects yet."
          description="Create your first research project above."
        />
      ) : (
        <div
          className="rounded-lg overflow-hidden"
          style={{ border: "1px solid var(--tron-border)", background: "var(--tron-bg-panel)" }}
        >
          {/* Table header */}
          <div
            className="grid items-center gap-4 px-4 py-2.5 text-[10px] font-semibold uppercase tracking-wider"
            style={{
              borderBottom: "1px solid var(--tron-border)",
              color: "var(--tron-text-muted)",
              gridTemplateColumns: "1fr 120px 90px 70px 60px 80px",
              background: "var(--tron-bg)",
            }}
          >
            <span>Target / Question</span>
            <span>Project ID</span>
            <span>Status</span>
            <span>Phase</span>
            <span className="text-right">Findings</span>
            <span>Started</span>
          </div>

          {/* Table rows */}
          <div className="divide-y" style={{ borderColor: "var(--tron-border)" }}>
            {projects.map((p) => {
              const progress = phaseProgress(p.phase);
              const isActive = !["done", "failed", "cancelled"].includes(p.status) && !p.status.startsWith("failed_");
              return (
                <Link
                  key={p.id}
                  href={`/research/${p.id}`}
                  className="interactive-row grid items-center gap-4 px-4 py-3 text-[13px]"
                  style={{ gridTemplateColumns: "1fr 120px 90px 70px 60px 80px" }}
                >
                  {/* Question + progress bar */}
                  <div className="min-w-0">
                    <p className="truncate font-medium leading-tight" style={{ color: "var(--tron-text)" }}>
                      {p.question || "Untitled"}
                    </p>
                    <ProjectRowProgress
                      projectId={p.id}
                      isActive={isActive}
                      status={p.status}
                      progressPercent={progress}
                    />
                  </div>

                  {/* Project ID (short) */}
                  <span className="font-mono text-[10px] truncate" style={{ color: "var(--tron-text-dim)" }}>
                    {p.id.replace("proj-", "")}
                  </span>

                  {/* Status badge */}
                  <div>
                    <StatusBadge status={p.status} />
                  </div>

                  {/* Current phase */}
                  <span
                    className="font-mono text-[10px] uppercase font-semibold"
                    style={{ color: isActive ? "var(--tron-accent)" : "var(--tron-text-dim)" }}
                  >
                    {p.phase}
                  </span>

                  {/* Findings count */}
                  <span className="text-right font-mono text-sm font-semibold" style={{ color: "var(--tron-text)" }}>
                    {p.findings_count}
                  </span>

                  {/* Started date */}
                  <span className="text-[11px]" style={{ color: "var(--tron-text-dim)" }}>
                    {formatDate(p.created_at)}
                  </span>
                </Link>
              );
            })}
          </div>

          {/* Footer */}
          <div
            className="px-4 py-2 text-[11px]"
            style={{
              borderTop: "1px solid var(--tron-border)",
              background: "var(--tron-bg)",
              color: "var(--tron-text-dim)",
            }}
          >
            {projects.length} project{projects.length !== 1 ? "s" : ""} total
          </div>
        </div>
      )}
    </div>
  );
}
