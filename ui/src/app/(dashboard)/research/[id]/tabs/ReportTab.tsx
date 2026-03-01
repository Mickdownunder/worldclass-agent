"use client";

import { useState, useEffect } from "react";
import { MarkdownView } from "@/components/MarkdownView";
import { LoadingSpinner } from "@/components/LoadingSpinner";
import type { ProjectForReport } from "../types";

interface ReportTabProps {
  projectId: string;
  initialMarkdown: string | null;
  hasPdf: boolean;
  hasMasterDossier?: boolean;
  project?: ProjectForReport | null;
  onVerifiedClick: (claimId: string | undefined) => void;
  loading: boolean;
  onSwitchToCritique?: () => void;
}

export function ReportTab({
  projectId,
  initialMarkdown,
  hasPdf,
  hasMasterDossier = false,
  project,
  onVerifiedClick,
  loading,
  onSwitchToCritique,
}: ReportTabProps) {
  const [pdfMessage, setPdfMessage] = useState<string | null>(null);
  const [pdfGenerating, setPdfGenerating] = useState(false);
  const [masterPdfLoading, setMasterPdfLoading] = useState(false);
  const [critiquePreview, setCritiquePreview] = useState<{ weaknesses: string[] } | null>(null);
  const [critiqueExpanded, setCritiqueExpanded] = useState(false);

  useEffect(() => {
    if (project?.quality_gate?.critic_score == null) return;
    let cancelled = false;
    fetch(`/api/research/projects/${projectId}/critique`)
      .then((r) => (r.ok ? r.json() : null))
      .then((d) => {
        if (!cancelled && d?.weaknesses?.length) setCritiquePreview({ weaknesses: d.weaknesses });
      })
      .catch(() => {});
    return () => { cancelled = true; };
  }, [projectId, project?.quality_gate?.critic_score]);
  if (loading) return <LoadingSpinner />;
  if (!initialMarkdown) {
    return (
      <div className="py-10 text-center">
        <p className="text-sm" style={{ color: "var(--tron-text-muted)" }}>No report generated yet.</p>
        <p className="mt-1 text-xs" style={{ color: "var(--tron-text-dim)" }}>
          Complete the Synthesize phase to generate a report.
        </p>
      </div>
    );
  }

  const wordCount = initialMarkdown.trim().split(/\s+/).filter(Boolean).length;
  const h2Matches = initialMarkdown.match(/^##\s+(.+)$/gm) ?? [];
  const tocEntries = h2Matches.map((line) => line.replace(/^##\s+/, "").trim());
  const slug = (t: string) =>
    t.replace(/[^\w\s-]/g, "").trim().replace(/\s+/g, "-").toLowerCase().slice(0, 50);

  return (
    <>
      <div
        className="mb-3 grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-6 gap-2 text-[11px] font-mono"
        style={{ color: "var(--tron-text-muted)" }}
      >
        <div>Report as of: <span style={{ color: "var(--tron-text)" }}>{project?.last_phase_at ? new Date(project.last_phase_at).toISOString().slice(0, 10) : "—"}</span></div>
        <div>Quality score: <span style={{ color: "var(--tron-text)" }}>{project?.quality_gate?.critic_score != null ? String(project.quality_gate.critic_score) : "—"}</span></div>
        <div>Word count: <span style={{ color: "var(--tron-text)" }}>{wordCount.toLocaleString("en-US")}</span></div>
        <div>Sources: <span style={{ color: "var(--tron-text)" }}>{project?.quality_gate?.evidence_gate?.metrics?.unique_source_count ?? "—"}</span></div>
        <div>Spend: <span style={{ color: "var(--tron-text)" }}>{project?.current_spend != null ? `$${project.current_spend.toFixed(2)}` : "—"}</span></div>
        <div>Verified: <span style={{ color: "var(--tron-text)" }}>{project?.quality_gate?.evidence_gate?.metrics?.verified_claim_count != null ? String(project.quality_gate.evidence_gate?.metrics?.verified_claim_count) : "—"}</span></div>
        {critiquePreview && critiquePreview.weaknesses.length > 0 && (
          <div className="col-span-2 sm:col-span-3 lg:col-span-6 mt-1">
            <button
              type="button"
              onClick={() => setCritiqueExpanded((e) => !e)}
              className="text-left w-full rounded border py-1.5 px-2 text-[11px] font-mono flex items-center justify-between gap-2"
              style={{ borderColor: "var(--tron-border)", background: "var(--tron-bg-panel)", color: "var(--tron-text-muted)" }}
            >
              <span>Critic weaknesses (first {Math.min(2, critiquePreview.weaknesses.length)})</span>
              <span style={{ color: "var(--tron-accent)" }}>{critiqueExpanded ? "▼" : "▶"}</span>
            </button>
            {critiqueExpanded && (
              <ul className="mt-1 space-y-0.5 pl-2 text-[11px] border-l-2" style={{ color: "var(--tron-text-dim)", borderColor: "var(--tron-error, #e53e3e)" }}>
                {critiquePreview.weaknesses.slice(0, 2).map((w, i) => (
                  <li key={i} className="truncate max-w-full" title={w}>{w}</li>
                ))}
                {onSwitchToCritique && (
                  <li className="mt-1">
                    <button
                      type="button"
                      onClick={onSwitchToCritique}
                      className="font-semibold hover:underline"
                      style={{ color: "var(--tron-accent)" }}
                    >
                      View full critique →
                    </button>
                  </li>
                )}
              </ul>
            )}
          </div>
        )}
      </div>
      <div className="mb-3 flex items-center justify-between gap-3">
        <p className="text-[11px] font-mono" style={{ color: "var(--tron-text-dim)" }}>
          <span className="verified-badge-inline" style={{ cursor: "default" }}>VERIFIED</span> = cross-checked (2+ sources);{" "}
          <span style={{ color: "var(--tron-accent)" }}>AUTHORITATIVE</span> = single primary source (e.g. arxiv, official docs). Click badges to view evidence.
        </p>
        <div className="flex items-center gap-2 flex-wrap">
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
                  a.download = d.filename || `report-${projectId}.md`;
                  a.click();
                  URL.revokeObjectURL(url);
                });
            }}
            className="shrink-0 flex items-center gap-1.5 rounded px-3 py-1.5 text-[11px] font-semibold transition-colors"
            style={{ border: "1px solid var(--tron-border)", color: "var(--tron-text-muted)", background: "transparent" }}
            onMouseEnter={(e) => { e.currentTarget.style.borderColor = "var(--tron-accent)"; e.currentTarget.style.color = "var(--tron-accent)"; }}
            onMouseLeave={(e) => { e.currentTarget.style.borderColor = "var(--tron-border)"; e.currentTarget.style.color = "var(--tron-text-muted)"; }}
          >
            <svg width="12" height="12" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round"><path d="M6 1v8M2 7l4 4 4-4M1 13h10" /></svg>
            Download .md
          </button>
          {hasMasterDossier && (
            <button
              type="button"
              disabled={masterPdfLoading}
              onClick={async () => {
                setMasterPdfLoading(true);
                try {
                  const res = await fetch(`/api/research/projects/${projectId}/report/pdf/master`);
                  if (!res.ok) {
                    const d = await res.json().catch(() => ({}));
                    setPdfMessage(d?.error || "Master PDF failed");
                    return;
                  }
                  const blob = await res.blob();
                  const url = URL.createObjectURL(blob);
                  const a = document.createElement("a");
                  a.href = url;
                  a.download = "MASTER_DOSSIER.pdf";
                  a.click();
                  URL.revokeObjectURL(url);
                } finally {
                  setMasterPdfLoading(false);
                }
              }}
              className="shrink-0 flex items-center gap-1.5 rounded px-3 py-1.5 text-[11px] font-semibold transition-colors"
              style={{ border: "1px solid var(--tron-accent)", color: "var(--tron-accent)", background: "transparent" }}
              onMouseEnter={(e) => { e.currentTarget.style.background = "var(--tron-accent)"; e.currentTarget.style.color = "var(--tron-bg)"; }}
              onMouseLeave={(e) => { e.currentTarget.style.background = "transparent"; e.currentTarget.style.color = "var(--tron-accent)"; }}
            >
              {masterPdfLoading ? "…" : (
                <>
                  <svg width="12" height="12" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round"><path d="M6 1v8M2 7l4 4 4-4M1 13h10" /></svg>
                  Download Master PDF
                </>
              )}
            </button>
          )}
          {!hasPdf && (
            <button
              type="button"
              disabled={pdfGenerating}
              onClick={async () => {
                setPdfGenerating(true);
                setPdfMessage(null);
                try {
                  const res = await fetch(`/api/research/projects/${projectId}/report/pdf`, { method: "POST" });
                  const data = res.ok ? null : await res.json().catch(() => ({}));
                  if (!res.ok) {
                    setPdfMessage(data?.error ?? "PDF generation failed.");
                    setTimeout(() => setPdfMessage(null), 5000);
                    return;
                  }
                  const pdfRes = await fetch(`/api/research/projects/${projectId}/report/pdf`);
                  if (!pdfRes.ok) {
                    setPdfMessage("PDF created but download failed.");
                    setTimeout(() => setPdfMessage(null), 3000);
                    return;
                  }
                  const blob = await pdfRes.blob();
                  const url = URL.createObjectURL(blob);
                  const a = document.createElement("a");
                  a.href = url;
                  a.download = `report-${projectId}.pdf`;
                  a.click();
                  URL.revokeObjectURL(url);
                  setPdfMessage("PDF downloaded.");
                  setTimeout(() => setPdfMessage(null), 2000);
                } finally {
                  setPdfGenerating(false);
                }
              }}
              className="shrink-0 flex items-center gap-1.5 rounded px-3 py-1.5 text-[11px] font-semibold transition-colors disabled:opacity-60"
              style={{ border: "1px solid var(--tron-border)", color: "var(--tron-text-muted)", background: "transparent" }}
              onMouseEnter={(e) => { if (!pdfGenerating) { e.currentTarget.style.borderColor = "var(--tron-accent)"; e.currentTarget.style.color = "var(--tron-accent)"; } }}
              onMouseLeave={(e) => { e.currentTarget.style.borderColor = "var(--tron-border)"; e.currentTarget.style.color = "var(--tron-text-muted)"; }}
            >
              {pdfGenerating ? "Generating…" : "Generate PDF"}
            </button>
          )}
          {hasPdf && (
            <button
              type="button"
              onClick={async () => {
                const res = await fetch(`/api/research/projects/${projectId}/report/pdf`);
                if (!res.ok) {
                  if (res.status === 404) { setPdfMessage("PDF not available yet."); setTimeout(() => setPdfMessage(null), 3000); }
                  return;
                }
                const blob = await res.blob();
                const url = URL.createObjectURL(blob);
                const a = document.createElement("a");
                a.href = url;
                a.download = `report-${projectId}.pdf`;
                a.click();
                URL.revokeObjectURL(url);
              }}
              className="shrink-0 flex items-center gap-1.5 rounded px-3 py-1.5 text-[11px] font-semibold transition-colors"
              style={{ border: "1px solid var(--tron-border)", color: "var(--tron-text-muted)", background: "transparent" }}
              onMouseEnter={(e) => { e.currentTarget.style.borderColor = "var(--tron-accent)"; e.currentTarget.style.color = "var(--tron-accent)"; }}
              onMouseLeave={(e) => { e.currentTarget.style.borderColor = "var(--tron-border)"; e.currentTarget.style.color = "var(--tron-text-muted)"; }}
            >
              <svg width="12" height="12" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" viewBox="0 0 24 24">
                <path d="M14 2H6a2 2 0 00-2 2v16a2 2 0 002 2h12a2 2 0 002-2V8z" />
                <path d="M14 2v6h6M16 13H8M16 17H8M10 9H8" />
              </svg>
              Download PDF
            </button>
          )}
          {pdfMessage && <span className="text-[11px]" style={{ color: "var(--tron-text-dim)" }}>{pdfMessage}</span>}
        </div>
      </div>
      <div className="flex gap-4">
        <div
          className="flex-1 min-w-0 overflow-auto rounded-md p-6"
          style={{ background: "var(--tron-bg)", border: "1px solid var(--tron-border)", maxHeight: "72vh" }}
        >
          <MarkdownView
            content={initialMarkdown}
            className="report-prose"
            onVerifiedClick={onVerifiedClick}
            headingIds={true}
          />
        </div>
        {tocEntries.length >= 2 && (
          <div
            className="hidden lg:block shrink-0 w-48 sticky top-4 self-start rounded border py-3 px-3 text-[11px]"
            style={{ background: "var(--tron-bg-panel)", borderColor: "var(--tron-border)", maxHeight: "70vh", overflowY: "auto" }}
          >
            <div className="font-semibold uppercase tracking-wider mb-2" style={{ color: "var(--tron-text-muted)" }}>Contents</div>
            <ul className="space-y-1">
              {tocEntries.map((title) => (
                <li key={title}>
                  <button
                    type="button"
                    className="text-left w-full hover:underline truncate block"
                    style={{ color: "var(--tron-accent)" }}
                    onClick={() => document.getElementById(slug(title))?.scrollIntoView({ behavior: "smooth" })}
                  >
                    {title}
                  </button>
                </li>
              ))}
            </ul>
          </div>
        )}
      </div>
    </>
  );
}
