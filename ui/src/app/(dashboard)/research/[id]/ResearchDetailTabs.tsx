"use client";

import { useState, useEffect } from "react";
import { MarkdownView } from "@/components/MarkdownView";
import { LoadingSpinner } from "@/components/LoadingSpinner";
import { VerifiedClaimSlideover } from "@/components/VerifiedClaimSlideover";

type TabId = "report" | "findings" | "sources" | "verlauf" | "audit";

const FEEDBACK_TYPES = [
  { type: "excellent",  label: "Excellent" },
  { type: "ignore",     label: "Irrelevant" },
  { type: "wrong",      label: "Incorrect" },
  { type: "dig_deeper", label: "Dig Deeper" },
] as const;

interface Finding {
  id: string;
  url?: string;
  title?: string;
  excerpt?: string;
  source?: string;
  confidence?: number;
}

interface Source {
  id: string;
  url?: string;
  type?: string;
  confidence?: number;
  reliability_score?: number;
  score_source?: "initial" | "verified";
}

interface ReportEntry {
  filename: string;
  content: string;
}

interface AuditClaim {
  claim_id: string;
  text: string;
  is_verified: boolean;
  verification_reason?: string;
  supporting_source_ids: string[];
}

export function ResearchDetailTabs({
  projectId,
  initialMarkdown,
}: {
  projectId: string;
  initialMarkdown: string | null;
}) {
  const [activeTab, setActiveTab] = useState<TabId>("report");
  const [findings, setFindings] = useState<Finding[] | null>(null);
  const [sources, setSources] = useState<Source[] | null>(null);
  const [reports, setReports] = useState<ReportEntry[] | null>(null);
  const [auditClaims, setAuditClaims] = useState<AuditClaim[] | null>(null);
  const [loading, setLoading] = useState<Record<TabId, boolean>>({
    report: false, findings: false, sources: false, verlauf: false, audit: false,
  });
  const [slideoverTarget, setSlideoverTarget] = useState<{
    open: boolean;
    claimId?: string;
  }>({ open: false });

  useEffect(() => {
    if (activeTab === "findings" && findings === null) {
      setLoading((l) => ({ ...l, findings: true }));
      fetch(`/api/research/projects/${projectId}/findings`)
        .then((r) => r.json())
        .then((d) => setFindings(d.findings ?? []))
        .finally(() => setLoading((l) => ({ ...l, findings: false })));
    }
    if (activeTab === "sources" && sources === null) {
      setLoading((l) => ({ ...l, sources: true }));
      fetch(`/api/research/projects/${projectId}/sources`)
        .then((r) => r.json())
        .then((d) => setSources(d.sources ?? []))
        .finally(() => setLoading((l) => ({ ...l, sources: false })));
    }
    if (activeTab === "verlauf" && reports === null) {
      setLoading((l) => ({ ...l, verlauf: true }));
      fetch(`/api/research/projects/${projectId}/reports`)
        .then((r) => r.json())
        .then((d) => setReports(d.reports ?? []))
        .finally(() => setLoading((l) => ({ ...l, verlauf: false })));
    }
    if (activeTab === "audit" && auditClaims === null) {
      setLoading((l) => ({ ...l, audit: true }));
      fetch(`/api/research/projects/${projectId}/audit`)
        .then((r) => r.json())
        .then((d) => setAuditClaims(d.claims ?? []))
        .catch(() => setAuditClaims([]))
        .finally(() => setLoading((l) => ({ ...l, audit: false })));
    }
  }, [activeTab, projectId, findings, sources, reports, auditClaims]);

  async function sendFeedback(findingId: string, type: string) {
    try {
      await fetch("/api/research/feedback", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ project_id: projectId, type, finding_id: findingId }),
      });
    } catch { /* silent */ }
  }

  async function downloadReport(filename: string, content: string) {
    const blob = new Blob([content], { type: "text/markdown" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = filename;
    a.click();
    URL.revokeObjectURL(url);
  }

  const tabs: { id: TabId; label: string }[] = [
    { id: "report",   label: "Report" },
    { id: "findings", label: "Findings" },
    { id: "sources",  label: "Sources" },
    { id: "verlauf",  label: "History" },
    { id: "audit",    label: "Audit" },
  ];

  return (
    <div className="space-y-0">
      {/* Tab bar */}
      <div
        className="flex items-end gap-px px-0 overflow-x-auto"
        style={{ borderBottom: "1px solid var(--tron-border)" }}
      >
        {tabs.map((t) => (
          <button
            key={t.id}
            type="button"
            onClick={() => setActiveTab(t.id)}
            className="relative shrink-0 px-4 py-2.5 text-[12px] font-semibold uppercase tracking-wider transition-colors"
            style={{
              color: activeTab === t.id ? "var(--tron-accent)" : "var(--tron-text-muted)",
              background: "transparent",
              borderBottom: activeTab === t.id ? "2px solid var(--tron-accent)" : "2px solid transparent",
              marginBottom: "-1px",
            }}
          >
            {t.label}
          </button>
        ))}
      </div>

      {/* Tab content */}
      <div className="pt-4">
        {/* ── REPORT ── */}
        {activeTab === "report" && (
          <div>
            {loading.report ? (
              <LoadingSpinner />
            ) : initialMarkdown ? (
              <>
                <div className="mb-3 flex items-center justify-between gap-3">
                  <p className="text-[11px] font-mono" style={{ color: "var(--tron-text-dim)" }}>
                    Click{" "}
                    <span className="verified-badge-inline" style={{ cursor: "default" }}>
                      VERIFIED
                    </span>{" "}
                    badges to view supporting evidence
                  </p>
                  <button
                    type="button"
                    onClick={() => {
                      fetch(`/api/research/projects/${projectId}/report`)
                        .then((r) => r.json())
                        .then((d) => {
                          const blob = new Blob([d.markdown ?? ""], { type: "text/markdown" });
                          const url = URL.createObjectURL(blob);
                          const a = document.createElement("a");
                          a.href = url;
                          a.download = `report-${projectId}.md`;
                          a.click();
                          URL.revokeObjectURL(url);
                        });
                    }}
                    className="shrink-0 flex items-center gap-1.5 rounded px-3 py-1.5 text-[11px] font-semibold transition-colors"
                    style={{
                      border: "1px solid var(--tron-border)",
                      color: "var(--tron-text-muted)",
                      background: "transparent",
                    }}
                    onMouseEnter={e => {
                      e.currentTarget.style.borderColor = "var(--tron-accent)";
                      e.currentTarget.style.color = "var(--tron-accent)";
                    }}
                    onMouseLeave={e => {
                      e.currentTarget.style.borderColor = "var(--tron-border)";
                      e.currentTarget.style.color = "var(--tron-text-muted)";
                    }}
                  >
                    <svg width="12" height="12" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round">
                      <path d="M6 1v8M2 7l4 4 4-4M1 13h10" />
                    </svg>
                    Download .md
                  </button>
                </div>
                <div
                  className="overflow-auto rounded-md p-6"
                  style={{
                    background: "var(--tron-bg)",
                    border: "1px solid var(--tron-border)",
                    maxHeight: "72vh",
                  }}
                >
                  <MarkdownView
                    content={initialMarkdown}
                    className="report-prose"
                    onVerifiedClick={(claimId) =>
                      setSlideoverTarget({ open: true, claimId })
                    }
                  />
                </div>
              </>
            ) : (
              <div className="py-10 text-center">
                <p className="text-sm" style={{ color: "var(--tron-text-muted)" }}>No report generated yet.</p>
                <p className="mt-1 text-xs" style={{ color: "var(--tron-text-dim)" }}>
                  Complete the Synthesize phase to generate a report.
                </p>
              </div>
            )}
          </div>
        )}

        {/* ── FINDINGS ── */}
        {activeTab === "findings" && (
          <div>
            {loading.findings ? (
              <LoadingSpinner />
            ) : findings && findings.length > 0 ? (
              <div className="space-y-2">
                {findings.map((f) => (
                  <div
                    key={f.id}
                    className="rounded-md"
                    style={{ border: "1px solid var(--tron-border)", background: "var(--tron-bg)" }}
                  >
                    <div className="px-4 py-3">
                      <div className="flex items-start justify-between gap-3">
                        <div className="min-w-0 flex-1">
                          <p className="text-sm font-medium leading-snug" style={{ color: "var(--tron-text)" }}>
                            {f.title || f.url || f.id}
                          </p>
                          {f.url && (
                            <a
                              href={f.url}
                              target="_blank"
                              rel="noopener noreferrer"
                              className="mt-0.5 block truncate text-[11px] hover:underline"
                              style={{ color: "var(--tron-accent)" }}
                            >
                              {f.url}
                            </a>
                          )}
                        </div>
                        {f.confidence != null && (
                          <span className="shrink-0 font-mono text-[10px] font-semibold px-1.5 py-0.5 rounded"
                            style={{
                              background: "var(--tron-panel-hover)",
                              border: "1px solid var(--tron-border)",
                              color: "var(--tron-text-muted)",
                            }}>
                            {Math.round(f.confidence * 100)}%
                          </span>
                        )}
                      </div>
                      {f.excerpt && (
                        <p className="mt-2 line-clamp-2 text-[12px] leading-relaxed" style={{ color: "var(--tron-text-muted)" }}>
                          {f.excerpt}
                        </p>
                      )}
                    </div>
                    <div
                      className="flex flex-wrap gap-1.5 px-4 py-2"
                      style={{ borderTop: "1px solid var(--tron-border)" }}
                    >
                      {FEEDBACK_TYPES.map(({ type, label }) => (
                        <button
                          key={type}
                          type="button"
                          onClick={() => sendFeedback(f.id, type)}
                          className="rounded px-2 py-1 text-[10px] font-semibold uppercase tracking-wider transition-colors"
                          style={{
                            border: "1px solid var(--tron-border)",
                            color: "var(--tron-text-dim)",
                            background: "transparent",
                          }}
                          onMouseEnter={e => {
                            e.currentTarget.style.borderColor = "var(--tron-accent)";
                            e.currentTarget.style.color = "var(--tron-accent)";
                          }}
                          onMouseLeave={e => {
                            e.currentTarget.style.borderColor = "var(--tron-border)";
                            e.currentTarget.style.color = "var(--tron-text-dim)";
                          }}
                        >
                          {label}
                        </button>
                      ))}
                    </div>
                  </div>
                ))}
              </div>
            ) : (
              <p className="py-8 text-center text-sm" style={{ color: "var(--tron-text-muted)" }}>
                No findings.
              </p>
            )}
          </div>
        )}

        {/* ── SOURCES ── */}
        {activeTab === "sources" && (
          <div>
            {loading.sources ? (
              <LoadingSpinner />
            ) : sources && sources.length > 0 ? (
              <table className="data-table">
                <thead>
                  <tr>
                    <th>URL / Source</th>
                    <th>Type</th>
                    <th>Reliability</th>
                  </tr>
                </thead>
                <tbody>
                  {sources.map((s) => (
                    <tr key={s.id}>
                      <td className="max-w-[340px]">
                        {s.url ? (
                          <a
                            href={s.url}
                            target="_blank"
                            rel="noopener noreferrer"
                            className="block truncate text-[12px] hover:underline"
                            style={{ color: "var(--tron-accent)" }}
                          >
                            {s.url}
                          </a>
                        ) : (
                          <span className="font-mono text-[11px]" style={{ color: "var(--tron-text-dim)" }}>
                            {s.id}
                          </span>
                        )}
                      </td>
                      <td>
                        {s.type && (
                          <span className="font-mono text-[10px] px-1.5 py-0.5 rounded"
                            style={{ background: "var(--tron-bg)", border: "1px solid var(--tron-border)", color: "var(--tron-text-muted)" }}>
                            {s.type}
                          </span>
                        )}
                      </td>
                      <td>
                        {s.score_source === "verified" && s.reliability_score != null ? (
                          <ReliabilityBar score={s.reliability_score} />
                        ) : (
                          <span className="text-[11px]" style={{ color: "var(--tron-text-dim)" }}>
                            pre-verify
                          </span>
                        )}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            ) : (
              <p className="py-8 text-center text-sm" style={{ color: "var(--tron-text-muted)" }}>No sources.</p>
            )}
          </div>
        )}

        {/* ── HISTORY ── */}
        {activeTab === "verlauf" && (
          <div>
            {loading.verlauf ? (
              <LoadingSpinner />
            ) : reports && reports.length > 0 ? (
              <div className="space-y-3">
                {reports.map((r) => (
                  <div
                    key={r.filename}
                    className="rounded-md overflow-hidden"
                    style={{ border: "1px solid var(--tron-border)" }}
                  >
                    <div
                      className="flex items-center justify-between gap-3 px-4 py-2.5"
                      style={{ background: "var(--tron-bg)", borderBottom: "1px solid var(--tron-border)" }}
                    >
                      <span className="font-mono text-[11px]" style={{ color: "var(--tron-text-muted)" }}>
                        {r.filename}
                      </span>
                      <button
                        type="button"
                        onClick={() => downloadReport(r.filename, r.content)}
                        className="text-[11px] font-medium px-2 py-1 rounded transition-colors"
                        style={{ border: "1px solid var(--tron-border)", color: "var(--tron-text-muted)", background: "transparent" }}
                        onMouseEnter={e => {
                          e.currentTarget.style.color = "var(--tron-accent)";
                          e.currentTarget.style.borderColor = "var(--tron-accent)";
                        }}
                        onMouseLeave={e => {
                          e.currentTarget.style.color = "var(--tron-text-muted)";
                          e.currentTarget.style.borderColor = "var(--tron-border)";
                        }}
                      >
                        Download
                      </button>
                    </div>
                    <div className="overflow-auto p-4" style={{ maxHeight: "200px", background: "var(--tron-bg-panel)" }}>
                      <MarkdownView content={r.content} className="prose-headings:text-xs prose-p:text-xs" />
                    </div>
                  </div>
                ))}
              </div>
            ) : (
              <p className="py-8 text-center text-sm" style={{ color: "var(--tron-text-muted)" }}>No history.</p>
            )}
          </div>
        )}

        {/* ── AUDIT ── */}
        {activeTab === "audit" && (
          <div>
            {loading.audit ? (
              <LoadingSpinner />
            ) : auditClaims && auditClaims.length > 0 ? (
              <div className="space-y-4">
                {/* Stats row */}
                <div className="grid grid-cols-3 gap-3">
                  <div className="stat-card">
                    <div className="metric-label">Verified</div>
                    <div className="mt-1 text-2xl font-bold font-mono" style={{ color: "var(--tron-success)" }}>
                      {auditClaims.filter((c) => c.is_verified).length}
                    </div>
                  </div>
                  <div className="stat-card">
                    <div className="metric-label">Unverified</div>
                    <div className="mt-1 text-2xl font-bold font-mono" style={{ color: "var(--tron-warning)" }}>
                      {auditClaims.filter((c) => !c.is_verified).length}
                    </div>
                  </div>
                  <div className="stat-card">
                    <div className="metric-label">Total Claims</div>
                    <div className="mt-1 text-2xl font-bold font-mono" style={{ color: "var(--tron-text)" }}>
                      {auditClaims.length}
                    </div>
                  </div>
                </div>

                {/* Claims table */}
                <table className="data-table">
                  <thead>
                    <tr>
                      <th style={{ width: 80 }}>Status</th>
                      <th>Claim</th>
                      <th style={{ width: 100 }}>Sources</th>
                    </tr>
                  </thead>
                  <tbody>
                    {auditClaims.map((c) => (
                      <tr key={c.claim_id}>
                        <td>
                          <span
                            className="inline-block rounded px-1.5 py-0.5 font-mono text-[9px] font-bold uppercase tracking-wider"
                            style={{
                              background: c.is_verified ? "rgba(34,197,94,0.10)" : "rgba(245,158,11,0.10)",
                              color: c.is_verified ? "#22c55e" : "#f59e0b",
                              border: c.is_verified ? "1px solid rgba(34,197,94,0.25)" : "1px solid rgba(245,158,11,0.25)",
                            }}
                          >
                            {c.is_verified ? "Verified" : "Unverified"}
                          </span>
                        </td>
                        <td>
                          <p className="text-[12px] leading-relaxed" style={{ color: "var(--tron-text)" }}>
                            {c.text}
                          </p>
                          {c.verification_reason && !c.is_verified && (
                            <p className="mt-0.5 text-[11px] italic" style={{ color: "var(--tron-text-dim)" }}>
                              {c.verification_reason}
                            </p>
                          )}
                        </td>
                        <td>
                          <span className="font-mono text-[11px]" style={{ color: "var(--tron-text-muted)" }}>
                            {c.supporting_source_ids.length}
                          </span>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            ) : (
              <div className="py-10 text-center">
                <p className="text-sm" style={{ color: "var(--tron-text-muted)" }}>No audit data.</p>
                <p className="mt-1 text-xs" style={{ color: "var(--tron-text-dim)" }}>
                  Verify artifacts (claim_evidence_map or claim_ledger) not found for this project.
                </p>
              </div>
            )}
          </div>
        )}
      </div>

      {/* Slide-over */}
      <VerifiedClaimSlideover
        isOpen={slideoverTarget.open}
        onClose={() => setSlideoverTarget({ open: false })}
        projectId={projectId}
        targetClaimId={slideoverTarget.claimId}
      />
    </div>
  );
}

function ReliabilityBar({ score }: { score: number }) {
  const pct = Math.round(score * 100);
  const color = score >= 0.75 ? "#22c55e" : score >= 0.5 ? "#f59e0b" : "#f43f5e";
  return (
    <div className="flex items-center gap-2">
      <div className="w-16 h-1.5 rounded-full overflow-hidden" style={{ background: "var(--tron-border)" }}>
        <div
          className="h-full rounded-full transition-all"
          style={{ width: `${pct}%`, background: color }}
        />
      </div>
      <span className="font-mono text-[10px] font-semibold" style={{ color, minWidth: "2.5rem" }}>
        {pct}%
      </span>
    </div>
  );
}
