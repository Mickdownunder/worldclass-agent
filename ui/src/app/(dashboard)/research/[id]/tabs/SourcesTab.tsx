"use client";

import { LoadingSpinner } from "@/components/LoadingSpinner";
import type { Source } from "../types";
import { ReliabilityBar } from "./ReliabilityBar";

interface SourcesTabProps {
  sources: Source[] | null;
  loading: boolean;
}

export function SourcesTab({ sources, loading }: SourcesTabProps) {
  if (loading) return <LoadingSpinner />;
  if (!sources || sources.length === 0) {
    return <p className="py-8 text-center text-sm" style={{ color: "var(--tron-text-muted)" }}>No sources.</p>;
  }
  return (
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
                <a href={s.url} target="_blank" rel="noopener noreferrer" className="block truncate text-[12px] hover:underline" style={{ color: "var(--tron-accent)" }}>
                  {s.url}
                </a>
              ) : (
                <span className="font-mono text-[11px]" style={{ color: "var(--tron-text-dim)" }}>{s.id}</span>
              )}
            </td>
            <td>
              {s.type && (
                <span className="font-mono text-[10px] px-1.5 py-0.5 rounded" style={{ background: "var(--tron-bg)", border: "1px solid var(--tron-border)", color: "var(--tron-text-muted)" }}>
                  {s.type}
                </span>
              )}
            </td>
            <td>
              {s.score_source === "verified" && s.reliability_score != null ? (
                <ReliabilityBar score={s.reliability_score} />
              ) : (
                <span className="text-[11px]" style={{ color: "var(--tron-text-dim)" }}>pre-verify</span>
              )}
            </td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}
