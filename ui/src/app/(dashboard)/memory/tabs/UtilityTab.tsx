"use client";

import { useState } from "react";
import { Pagination } from "./Pagination";

export function UtilityTab({ utility, loading }: { utility: any[] | null; loading: boolean }) {
  const [page, setPage] = useState(1);
  const itemsPerPage = 10;

  if (loading) {
    return <div className="text-tron-dim p-6">Lade Utility-Top Memories…</div>;
  }

  const list = Array.isArray(utility) ? utility : [];
  const totalPages = Math.ceil(list.length / itemsPerPage) || 1;
  const slice = list.slice((page - 1) * itemsPerPage, page * itemsPerPage);

  return (
    <div className="tron-panel p-6 relative overflow-hidden">
      {/* Background glow decoration */}
      <div className="absolute top-0 right-0 w-64 h-64 bg-tron-accent opacity-5 rounded-full blur-[100px] pointer-events-none"></div>

      <div className="flex items-end justify-between mb-6 border-b border-tron-border/30 pb-4">
        <div>
          <h2 className="text-xl font-medium text-tron-muted tracking-tight">Utility Rank (Top Memories)</h2>
          <p className="text-xs text-tron-dim mt-1.5 uppercase tracking-widest font-semibold opacity-70">
            Laplace-smoothed retrieval vs helpfulness
          </p>
        </div>
      </div>

      {list.length === 0 ? (
        <p className="text-tron-dim">Noch keine Utility-Daten gesammelt.</p>
      ) : (
        <div className="overflow-x-auto">
          <table className="w-full text-sm text-left border-collapse">
            <thead className="text-[10px] uppercase text-tron-dim tracking-wider border-b border-tron-border/60 bg-tron-bg/50">
              <tr>
                <th className="px-4 py-3 font-semibold w-16">Rank</th>
                <th className="px-4 py-3 font-semibold">Type</th>
                <th className="px-4 py-3 font-semibold">ID (Hash)</th>
                <th className="px-4 py-3 font-semibold text-right">Helpful / Retr.</th>
                <th className="px-4 py-3 font-semibold text-right">Utility Score</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-tron-border/30">
              {slice.map((row, i) => {
                const rank = (page - 1) * itemsPerPage + i + 1;
                return (
                  <tr key={`${row.memory_type}-${row.memory_id}`} className="hover:bg-tron-accent/5 transition-colors group">
                    <td className="px-4 py-3.5 font-mono text-tron-dim text-xs group-hover:text-tron-text transition-colors">
                      {rank.toString().padStart(2, '0')}
                    </td>
                    <td className="px-4 py-3.5">
                      <span className={`px-2 py-0.5 rounded text-[10px] font-medium tracking-wide uppercase ${row.memory_type === 'principle' ? 'text-[#c678ff] bg-[#c678ff]/10 border border-[#c678ff]/30' : 'text-tron-accent bg-tron-accent/10 border border-tron-accent/30'}`}>
                        {row.memory_type}
                      </span>
                    </td>
                    <td className="px-4 py-3.5 font-mono text-tron-text text-xs tracking-wider opacity-90">
                      {(row.memory_id || "").slice(0, 8)}…
                    </td>
                    <td className="px-4 py-3.5 text-right font-mono text-xs">
                      <span className="text-tron-text">{row.helpful_count}</span>
                      <span className="text-tron-dim/50 mx-1">/</span>
                      <span className="text-tron-dim">{row.retrieval_count}</span>
                    </td>
                    <td className="px-4 py-3.5 text-right">
                      <div className="flex items-center justify-end gap-3">
                        <div className="w-24 h-1.5 bg-tron-bg rounded-full overflow-hidden border border-tron-border/30">
                          <div 
                            className="h-full rounded-full"
                            style={{ 
                              width: `${(row.utility_score || 0) * 100}%`,
                              background: "linear-gradient(90deg, transparent, var(--tron-success))",
                              boxShadow: "0 0 5px var(--tron-success)"
                            }}
                          />
                        </div>
                        <span className="font-mono text-tron-success font-bold text-sm w-12">
                          {row.utility_score?.toFixed(2)}
                        </span>
                      </div>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}

      {list.length > 0 && (
        <div className="mt-6 border-t border-tron-border/30 pt-4">
          <Pagination currentPage={page} totalPages={totalPages} onPageChange={setPage} />
        </div>
      )}
    </div>
  );
}
