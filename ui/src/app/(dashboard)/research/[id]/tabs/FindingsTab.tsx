"use client";

import { LoadingSpinner } from "@/components/LoadingSpinner";
import type { Finding } from "../types";
import { FEEDBACK_TYPES } from "../types";

interface FindingsTabProps {
  findings: Finding[] | null;
  loading: boolean;
  onSendFeedback: (findingId: string, type: string) => void;
}

export function FindingsTab({ findings, loading, onSendFeedback }: FindingsTabProps) {
  if (loading) return <LoadingSpinner />;
  if (!findings || findings.length === 0) {
    return <p className="py-8 text-center text-sm" style={{ color: "var(--tron-text-muted)" }}>No findings.</p>;
  }
  return (
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
                  <a href={f.url} target="_blank" rel="noopener noreferrer" className="mt-0.5 block truncate text-[11px] hover:underline" style={{ color: "var(--tron-accent)" }}>
                    {f.url}
                  </a>
                )}
              </div>
              {f.confidence != null && (
                <span
                  className="shrink-0 font-mono text-[10px] font-semibold px-1.5 py-0.5 rounded"
                  style={{ background: "var(--tron-panel-hover)", border: "1px solid var(--tron-border)", color: "var(--tron-text-muted)" }}
                >
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
          <div className="flex flex-wrap gap-1.5 px-4 py-2" style={{ borderTop: "1px solid var(--tron-border)" }}>
            {FEEDBACK_TYPES.map(({ type, label }) => (
              <button
                key={type}
                type="button"
                onClick={() => onSendFeedback(f.id, type)}
                className="rounded px-2 py-1 text-[10px] font-semibold uppercase tracking-wider transition-colors"
                style={{ border: "1px solid var(--tron-border)", color: "var(--tron-text-dim)", background: "transparent" }}
                onMouseEnter={(e) => { e.currentTarget.style.borderColor = "var(--tron-accent)"; e.currentTarget.style.color = "var(--tron-accent)"; }}
                onMouseLeave={(e) => { e.currentTarget.style.borderColor = "var(--tron-border)"; e.currentTarget.style.color = "var(--tron-text-dim)"; }}
              >
                {label}
              </button>
            ))}
          </div>
        </div>
      ))}
    </div>
  );
}
