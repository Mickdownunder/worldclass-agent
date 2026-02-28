import React, { useState } from "react";
import { Pagination } from "./Pagination";

export function PrinciplesTab({ principles, loading }: { principles: unknown[] | null; loading: boolean }) {
  const [page, setPage] = useState(1);
  const itemsPerPage = 10;

  if (loading) {
    return <div className="text-tron-dim p-4">Lade Prinzipien...</div>;
  }
  
  interface PrincipleRow {
    id?: string;
    metric_score?: number;
    description?: string;
    principle_type?: string;
    domain?: string;
    usage_count?: number;
  }
  const sortedPrinciples = [...(principles ?? [])].sort(
    (a, b) => ((b as PrincipleRow).metric_score ?? 0) - ((a as PrincipleRow).metric_score ?? 0)
  );
  const totalPages = Math.ceil(sortedPrinciples.length / itemsPerPage);
  const displayedPrinciples = sortedPrinciples.slice((page - 1) * itemsPerPage, page * itemsPerPage);

  return (
    <div className="tron-panel p-6">
      <h2 className="mb-4 text-lg font-medium text-tron-muted">Strategic Principles</h2>
      <p className="mb-3 text-[12px] text-tron-dim">Guiding and cautionary principles from past research (EvolveR).</p>
      
      <div className="overflow-x-auto">
        <table className="w-full text-[12px] data-table">
          <thead>
            <tr className="text-left text-tron-dim border-b border-tron-border">
              <th className="pb-2 pr-4 w-24">Type</th>
              <th className="pb-2 pr-4">Description</th>
              <th className="pb-2 pr-4 w-32">Domain</th>
              <th className="pb-2 pr-4 w-24">Score</th>
              <th className="pb-2 w-16">Use</th>
            </tr>
          </thead>
          <tbody>
            {displayedPrinciples.map((p, i) => {
              const row = p as PrincipleRow;
              const score = row.metric_score ?? 0;
              const barColor = row.principle_type === "cautionary" ? "var(--tron-error)" : "var(--tron-success)";
              return (
                <tr key={row.id ?? i} className="border-b border-tron-border/50 interactive-row">
                  <td className="py-2 pr-4 align-top">
                    <span
                      className="rounded px-1.5 py-0.5 font-mono text-[10px] font-bold uppercase whitespace-nowrap"
                      style={{ background: "var(--tron-bg)", color: barColor }}
                    >
                      {row.principle_type ?? "guiding"}
                    </span>
                  </td>
                  <td className="py-2 pr-4 align-top">
                    <span className="text-tron-text" title={row.description}>
                      {(row.description ?? "").slice(0, 150)}
                      {(row.description?.length ?? 0) > 150 ? "…" : ""}
                    </span>
                  </td>
                  <td className="py-2 pr-4 align-top">
                    {row.domain && <span className="text-tron-accent text-[11px]">{row.domain}</span>}
                  </td>
                  <td className="py-2 pr-4 align-top">
                    <div className="flex items-center gap-2">
                      <span className="text-tron-dim w-8">{score.toFixed(2)}</span>
                      <div className="h-1.5 w-full bg-tron-border/50 rounded-full overflow-hidden">
                        <div className="h-full rounded-full" style={{ width: `${Math.max(0, Math.min(100, score * 10))}%`, background: barColor }} />
                      </div>
                    </div>
                  </td>
                  <td className="py-2 align-top text-tron-dim">
                    {row.usage_count ?? 0}
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
      {(principles?.length ?? 0) === 0 && <p className="text-tron-dim mt-4">Noch keine Prinzipien.</p>}
      
      <Pagination currentPage={page} totalPages={totalPages} onPageChange={setPage} />
    </div>
  );
}
