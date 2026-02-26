import React, { useState } from "react";
import { Pagination } from "./Pagination";

export function SourcesTab({ credibility, loading }: { credibility: any[] | null; loading: boolean }) {
  const [page, setPage] = useState(1);
  const itemsPerPage = 10;

  if (loading) {
    return <div className="text-tron-dim p-4">Lade Sources...</div>;
  }
  
  const allCredibility = credibility ?? [];
  const totalPages = Math.ceil(allCredibility.length / itemsPerPage);
  const displayedCredibility = allCredibility.slice((page - 1) * itemsPerPage, page * itemsPerPage);

  return (
    <div className="tron-panel p-6">
      <h2 className="mb-4 text-lg font-medium text-tron-muted">Source Credibility</h2>
      <p className="mb-3 text-[12px] text-tron-dim">Domain-level learned credibility from verification outcomes.</p>
      
      <div className="overflow-x-auto">
        <table className="w-full text-[12px] data-table">
          <thead>
            <tr className="text-left text-tron-dim border-b border-tron-border">
              <th className="pb-2 pr-4">Domain</th>
              <th className="pb-2 pr-4">Used</th>
              <th className="pb-2 pr-4">Verified</th>
              <th className="pb-2 pr-4">Failed</th>
              <th className="pb-2">Credibility</th>
            </tr>
          </thead>
          <tbody>
            {displayedCredibility.map((c, i) => {
              const cred = c.learned_credibility ?? 0;
              const credColor = cred >= 0.7 ? "var(--tron-success)" : cred >= 0.4 ? "var(--tron-warning, #f59e0b)" : "var(--tron-error)";
              return (
                <tr key={c.domain ?? i} className="border-b border-tron-border/50 interactive-row">
                  <td className="py-2 pr-4 font-mono text-tron-text">{c.domain}</td>
                  <td className="py-2 pr-4 text-tron-muted">{c.times_used ?? 0}</td>
                  <td className="py-2 pr-4 text-tron-muted">{c.verified_count ?? 0}</td>
                  <td className="py-2 pr-4 text-tron-muted">{c.failed_verification_count ?? 0}</td>
                  <td className="py-2 font-semibold" style={{ color: credColor }}>{(cred * 100).toFixed(0)}%</td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
      {allCredibility.length === 0 && <p className="text-tron-dim mt-4">Noch keine Credibility-Daten.</p>}
      
      <Pagination currentPage={page} totalPages={totalPages} onPageChange={setPage} />
    </div>
  );
}
