"use client";

import { useState } from "react";
import { Pagination } from "./Pagination";

export function StrategiesTab({ strategies, loading }: { strategies: any[] | null; loading: boolean }) {
  const [page, setPage] = useState(1);
  const itemsPerPage = 6;

  if (loading) {
    return <div className="text-tron-dim p-6">Lade Strategies…</div>;
  }

  const list = Array.isArray(strategies) ? strategies : [];
  const totalPages = Math.ceil(list.length / itemsPerPage) || 1;
  const slice = list.slice((page - 1) * itemsPerPage, page * itemsPerPage);

  return (
    <div className="tron-panel p-6">
      <h2 className="mb-4 text-lg font-medium text-tron-muted">Strategy Profiles</h2>
      <p className="text-sm text-tron-dim mb-4">
        Welche Strategies existieren, welche sind "empirical", deren Score und Konfidenz.
      </p>

      {list.length === 0 ? (
        <p className="text-tron-dim">Keine Strategy Profiles gefunden.</p>
      ) : (
        <div className="space-y-4">
          {slice.map((s, i) => (
            <div key={s.id || i} className="border border-tron-border rounded-lg p-4 text-sm flex flex-col gap-2">
              <div className="flex flex-wrap items-center gap-3">
                <span className="font-bold text-tron-accent">{s.name}</span>
                <span className="text-tron-dim text-xs">ID: {(s.id || "").slice(0, 8)}</span>
                <span className="px-2 py-0.5 rounded text-xs bg-tron-bg border border-tron-border">
                  Domain: {s.domain || "general"}
                </span>
                <span style={{ color: "var(--tron-success)" }}>Score: {s.score?.toFixed(2)}</span>
                <span className="text-tron-dim">Conf: {s.confidence?.toFixed(2)}</span>
              </div>
              {s.policy && (
                <div className="mt-2 bg-tron-bg/50 p-3 rounded text-[11px] font-mono text-tron-dim overflow-auto">
                  {JSON.stringify(s.policy, null, 2)}
                </div>
              )}
            </div>
          ))}
        </div>
      )}

      {list.length > 0 && (
        <div className="mt-4">
          <Pagination currentPage={page} totalPages={totalPages} onPageChange={setPage} />
        </div>
      )}
    </div>
  );
}
