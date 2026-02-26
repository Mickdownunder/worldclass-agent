"use client";

import { MarkdownView } from "@/components/MarkdownView";
import { LoadingSpinner } from "@/components/LoadingSpinner";
import type { ReportEntry } from "../types";

interface HistoryTabProps {
  reports: ReportEntry[] | null;
  loading: boolean;
  onDownloadReport: (filename: string, content: string) => void;
}

export function HistoryTab({ reports, loading, onDownloadReport }: HistoryTabProps) {
  if (loading) return <LoadingSpinner />;
  if (!reports || reports.length === 0) {
    return <p className="py-8 text-center text-sm" style={{ color: "var(--tron-text-muted)" }}>No history.</p>;
  }
  return (
    <div className="space-y-3">
      {reports.map((r) => (
        <div key={r.filename} className="rounded-md overflow-hidden" style={{ border: "1px solid var(--tron-border)" }}>
          <div className="flex items-center justify-between gap-3 px-4 py-2.5" style={{ background: "var(--tron-bg)", borderBottom: "1px solid var(--tron-border)" }}>
            <span className="font-mono text-[11px]" style={{ color: "var(--tron-text-muted)" }}>{r.filename}</span>
            <button
              type="button"
              onClick={() => onDownloadReport(r.filename, r.content)}
              className="text-[11px] font-medium px-2 py-1 rounded transition-colors"
              style={{ border: "1px solid var(--tron-border)", color: "var(--tron-text-muted)", background: "transparent" }}
              onMouseEnter={(e) => { e.currentTarget.style.color = "var(--tron-accent)"; e.currentTarget.style.borderColor = "var(--tron-accent)"; }}
              onMouseLeave={(e) => { e.currentTarget.style.color = "var(--tron-text-muted)"; e.currentTarget.style.borderColor = "var(--tron-border)"; }}
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
  );
}
