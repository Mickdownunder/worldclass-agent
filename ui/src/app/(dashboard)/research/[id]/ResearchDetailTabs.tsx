"use client";

import { useState, useEffect } from "react";
import { MarkdownView } from "@/components/MarkdownView";
import { LoadingSpinner } from "@/components/LoadingSpinner";

type TabId = "report" | "findings" | "sources" | "verlauf" | "audit";

const FEEDBACK_TYPES = [
  { type: "excellent", label: "Excellent" },
  { type: "ignore", label: "Irrelevant" },
  { type: "wrong", label: "Falsch" },
  { type: "dig_deeper", label: "Tiefer graben" },
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
    report: false,
    findings: false,
    sources: false,
    verlauf: false,
    audit: false,
  });

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
        body: JSON.stringify({
          project_id: projectId,
          type,
          finding_id: findingId,
        }),
      });
    } catch {
      //
    }
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
    { id: "report", label: "Report" },
    { id: "findings", label: "Findings" },
    { id: "sources", label: "Quellen" },
    { id: "verlauf", label: "Verlauf" },
    { id: "audit", label: "Audit" },
  ];

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap gap-2 rounded-sm bg-tron-panel border border-tron-border p-2">
        {tabs.map((t) => (
          <button
            key={t.id}
            type="button"
            onClick={() => setActiveTab(t.id)}
            className={`min-h-[36px] flex-1 min-w-[100px] rounded-sm px-4 py-1.5 text-sm font-bold uppercase tracking-wider transition-all ${
              activeTab === t.id
                ? "bg-tron-accent text-black shadow-[0_0_10px_var(--tron-glow)]"
                : "text-tron-muted hover:bg-tron-accent/10 hover:text-tron-accent hover:shadow-[0_0_10px_var(--tron-glow)]"
            }`}
          >
            {t.label}
          </button>
        ))}
      </div>

      {activeTab === "report" && (
        <div className="tron-panel p-4">
          {loading.report ? (
            <LoadingSpinner />
          ) : initialMarkdown ? (
            <>
              <div className="mb-3 flex justify-end">
                <button
                  type="button"
                  onClick={() => {
                    fetch(`/api/research/projects/${projectId}/report`)
                      .then((r) => r.json())
                      .then((d) => {
                        const blob = new Blob([d.markdown ?? ""], {
                          type: "text/markdown",
                        });
                        const url = URL.createObjectURL(blob);
                        const a = document.createElement("a");
                        a.href = url;
                        a.download = `report-${projectId}.md`;
                        a.click();
                        URL.revokeObjectURL(url);
                      });
                  }}
                  className="rounded-sm border-2 border-tron-accent bg-transparent px-3 py-1.5 text-xs font-bold text-tron-accent uppercase tracking-wider hover:bg-tron-accent hover:text-black hover:shadow-[0_0_10px_var(--tron-glow)] transition-all"
                >
                  Download .md
                </button>
              </div>
              <div className="max-h-[70vh] overflow-auto rounded bg-tron-bg p-6 border border-tron-border/30 shadow-[inset_0_0_20px_rgba(0,0,0,0.5)]">
                <MarkdownView content={initialMarkdown} className="report-prose" />
              </div>
            </>
          ) : (
            <p className="text-tron-dim">Noch kein Report.</p>
          )}
        </div>
      )}

      {activeTab === "findings" && (
        <div className="tron-panel p-4">
          {loading.findings ? (
            <LoadingSpinner />
          ) : findings && findings.length > 0 ? (
            <ul className="space-y-4">
              {findings.map((f) => (
                <li
                  key={f.id}
                  className="rounded-sm border-2 border-tron-border bg-tron-bg p-4 shadow-[0_0_10px_var(--tron-glow)]"
                >
                  <div className="font-medium text-tron-text">
                    {f.title || f.url || f.id}
                  </div>
                  {f.url && (
                    <a
                      href={f.url}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="text-xs text-tron-accent hover:underline"
                    >
                      {f.url}
                    </a>
                  )}
                  {f.excerpt && (
                    <p className="mt-1 line-clamp-3 text-sm text-tron-muted">
                      {f.excerpt}
                    </p>
                  )}
                  <div className="mt-2 flex flex-wrap gap-2">
                    {FEEDBACK_TYPES.map(({ type, label }) => (
                      <button
                        key={type}
                        type="button"
                        onClick={() => sendFeedback(f.id, type)}
                      className="rounded-sm border-2 border-tron-border bg-transparent px-3 py-1.5 text-xs font-bold text-tron-muted uppercase tracking-wider hover:border-tron-accent hover:text-tron-accent hover:shadow-[0_0_10px_var(--tron-glow)] transition-all"
                      >
                        {label}
                      </button>
                    ))}
                  </div>
                </li>
              ))}
            </ul>
          ) : (
            <p className="text-tron-dim">Keine Findings.</p>
          )}
        </div>
      )}

      {activeTab === "sources" && (
        <div className="tron-panel p-4">
          {loading.sources ? (
            <LoadingSpinner />
          ) : sources && sources.length > 0 ? (
            <ul className="space-y-2 text-sm">
              {sources.map((s) => (
                <li key={s.id} className="flex flex-wrap items-center gap-2">
                  {s.url ? (
                    <a
                      href={s.url}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="text-tron-accent hover:underline"
                    >
                      {s.url}
                    </a>
                  ) : (
                    <span className="text-tron-dim">{s.id}</span>
                  )}
                  {s.type != null && (
                    <span className="text-tron-muted">({s.type})</span>
                  )}
                  {s.score_source === "verified" && s.reliability_score != null ? (
                    <span className="rounded border border-tron-accent/50 bg-tron-accent/10 px-2 py-0.5 text-xs font-medium text-tron-accent" title="Verified reliability (post-verify)">
                      Reliability: {Math.round(s.reliability_score * 100)}%
                    </span>
                  ) : (
                    <span className="rounded border border-tron-border bg-tron-bg px-2 py-0.5 text-xs text-tron-muted" title="Initial confidence before verify; not a final quality verdict">
                      unrated (pre-verify)
                    </span>
                  )}
                </li>
              ))}
            </ul>
          ) : (
            <p className="text-tron-dim">Keine Quellen.</p>
          )}
        </div>
      )}

      {activeTab === "verlauf" && (
        <div className="tron-panel p-4">
          {loading.verlauf ? (
            <LoadingSpinner />
          ) : reports && reports.length > 0 ? (
            <ul className="space-y-4">
              {reports.map((r) => (
                <li key={r.filename} className="border-b border-tron-border pb-4">
                  <div className="mb-2 flex items-center justify-between gap-2">
                    <span className="font-mono text-sm text-tron-accent">
                      {r.filename}
                    </span>
                    <button
                      type="button"
                      onClick={() => downloadReport(r.filename, r.content)}
                  className="rounded-sm border-2 border-tron-accent bg-transparent px-3 py-1.5 text-xs font-bold text-tron-accent uppercase tracking-wider hover:bg-tron-accent hover:text-black hover:shadow-[0_0_10px_var(--tron-glow)] transition-all"
                    >
                      Download
                    </button>
                  </div>
                  <div className="max-h-48 overflow-auto rounded bg-tron-bg p-3">
                    <MarkdownView
                      content={r.content}
                      className="prose-headings:text-sm prose-p:text-xs"
                    />
                  </div>
                </li>
              ))}
            </ul>
          ) : (
            <p className="text-tron-dim">Kein Verlauf.</p>
          )}
        </div>
      )}

      {activeTab === "audit" && (
        <div className="tron-panel p-4">
          {loading.audit ? (
            <LoadingSpinner />
          ) : auditClaims && auditClaims.length > 0 ? (
            <div className="space-y-4">
              <div className="grid gap-4 md:grid-cols-3">
                <div className="rounded-sm border-2 border-tron-border bg-tron-bg p-3">
                  <div className="text-xs font-bold uppercase text-tron-muted">
                    Verified
                  </div>
                  <div className="mt-1 text-lg font-bold text-green-500">
                    {auditClaims.filter((c) => c.is_verified).length}
                  </div>
                </div>
                <div className="rounded-sm border-2 border-tron-border bg-tron-bg p-3">
                  <div className="text-xs font-bold uppercase text-tron-muted">
                    Unverified / Disputed
                  </div>
                  <div className="mt-1 text-lg font-bold text-amber-500">
                    {auditClaims.filter((c) => !c.is_verified).length}
                  </div>
                </div>
                <div className="rounded-sm border-2 border-tron-border bg-tron-bg p-3">
                  <div className="text-xs font-bold uppercase text-tron-muted">
                    Total claims
                  </div>
                  <div className="mt-1 text-lg font-bold text-tron-accent">
                    {auditClaims.length}
                  </div>
                </div>
              </div>
              <ul className="space-y-3">
                {auditClaims.map((c) => (
                  <li
                    key={c.claim_id}
                    className={`rounded-sm border-2 p-3 ${
                      c.is_verified
                        ? "border-green-500/50 bg-green-500/5"
                        : "border-tron-border bg-tron-bg"
                    }`}
                  >
                    <div className="flex items-center gap-2">
                      <span
                        className={`rounded px-2 py-0.5 text-xs font-bold uppercase ${
                          c.is_verified
                            ? "bg-green-500/20 text-green-400"
                            : "bg-amber-500/20 text-amber-400"
                        }`}
                      >
                        {c.is_verified
                          ? "Verified"
                          : c.verification_reason?.toLowerCase().includes("dispute")
                            ? "Disputed"
                            : "Unverified"}
                      </span>
                      {c.verification_reason && !c.is_verified && (
                        <span className="text-xs text-tron-muted">
                          {c.verification_reason}
                        </span>
                      )}
                    </div>
                    <p className="mt-1 text-sm text-tron-text">{c.text}</p>
                    {c.supporting_source_ids.length > 0 && (
                      <div className="mt-2 flex flex-wrap gap-1">
                        {c.supporting_source_ids.map((sid) => (
                          <span
                            key={sid}
                            className="rounded bg-tron-panel px-2 py-0.5 font-mono text-xs text-tron-accent"
                          >
                            {sid}
                          </span>
                        ))}
                      </div>
                    )}
                  </li>
                ))}
              </ul>
            </div>
          ) : (
            <p className="text-tron-dim">
              Keine Audit-Daten. Verify-Artefakte (claim_evidence_map oder
              claim_ledger) fehlen für dieses Projekt.
            </p>
          )}
        </div>
      )}
    </div>
  );
}
