"use client";

import type { RunEpisodeRow } from "@/lib/operator/memory";
import { Pagination } from "./Pagination";
import { useState } from "react";

export function RunsTab({ runs }: { runs: RunEpisodeRow[] }) {
  const [page, setPage] = useState(1);
  const perPage = 10;
  const totalPages = Math.max(1, Math.ceil((runs?.length ?? 0) / perPage));
  const list = runs ?? [];
  const slice = list.slice((page - 1) * perPage, page * perPage);

  return (
    <div className="tron-panel p-6 flex flex-col">
      <h2 className="mb-4 text-lg font-medium text-tron-muted">
        Run Timeline
      </h2>
      <p className="text-sm text-tron-dim mb-6">
        Letzte Research-Runs als Timeline: Projekt, Strategy, Critic-Score, was half/schadete.
      </p>
      <div className="flex-1 relative">
        {/* Vertical timeline line */}
        {list.length > 0 && (
          <div className="absolute left-4 top-4 bottom-4 w-px bg-tron-accent/30 shadow-[0_0_8px_rgba(0,212,255,0.4)]" />
        )}

        {list.length === 0 ? (
          <p className="text-tron-dim pl-10">Noch keine Run-Episoden (v2).</p>
        ) : (
          <div className="space-y-6">
            {slice.map((r, idx) => (
              <div key={r.id} className="relative pl-12">
                {/* Timeline node */}
                <div 
                  className="absolute left-3 top-3 w-2.5 h-2.5 rounded-full" 
                  style={{ 
                    background: idx % 2 === 0 ? "var(--tron-accent)" : "#c678ff",
                    boxShadow: `0 0 10px ${idx % 2 === 0 ? "var(--tron-accent)" : "#c678ff"}` 
                  }} 
                />
                
                <div className="border border-tron-border/60 rounded-xl p-4 text-sm bg-tron-bg-panel/50 backdrop-blur-sm relative group hover:border-tron-accent/50 transition-colors">
                  <div className="flex flex-wrap items-baseline gap-x-4 gap-y-1 mb-2">
                    <span className="text-tron-dim font-mono text-xs">{r.created_at}</span>
                    <span className="font-semibold text-tron-text">{r.project_id}</span>
                  </div>
                  
                  <div className="flex items-center gap-2 mb-3">
                    <span className="text-tron-dim text-xs">Strategy:</span>
                    <span className="px-2 py-0.5 rounded text-xs font-mono text-tron-bg bg-[#c678ff] shadow-[0_0_5px_rgba(198,120,255,0.4)]">
                      {r.strategy_profile_id ? r.strategy_profile_id.slice(0, 16) : "default"}
                    </span>
                    {r.domain && (
                      <span className="text-[10px] text-tron-dim border border-tron-border px-1.5 py-0.5 rounded">
                        {r.domain}
                      </span>
                    )}
                  </div>

                  <div className="flex items-center gap-3 mb-4">
                    <span className="text-tron-dim text-xs">Critic Score:</span>
                    <div className="h-1.5 w-32 bg-tron-bg rounded-full overflow-hidden">
                      <div 
                        className="h-full rounded-full transition-all duration-500"
                        style={{ 
                          width: `${(r.critic_score ?? 0) * 100}%`,
                          background: (r.critic_score ?? 0) >= 0.7 ? "var(--tron-success)" : (r.critic_score ?? 0) >= 0.4 ? "var(--tron-accent)" : "var(--tron-error)",
                          boxShadow: `0 0 8px ${(r.critic_score ?? 0) >= 0.7 ? "var(--tron-success)" : (r.critic_score ?? 0) >= 0.4 ? "var(--tron-accent)" : "var(--tron-error)"}`
                        }}
                      />
                    </div>
                    <span className="font-mono text-xs text-tron-text">
                      {r.critic_score?.toFixed(2) ?? "—"}
                    </span>
                  </div>

                  <div className="space-y-1.5 text-xs">
                    {r.what_helped !== "—" && (
                      <div className="flex gap-2">
                        <span className="text-tron-success font-bold mt-px shrink-0">• WHAT HELPED</span>
                        <span className="text-tron-text">{r.what_helped}</span>
                      </div>
                    )}
                    {r.what_hurt !== "—" && (
                      <div className="flex gap-2">
                        <span className="text-[#c678ff] font-bold mt-px shrink-0">• WHAT HURT</span>
                        <span className="text-tron-text opacity-80">{r.what_hurt}</span>
                      </div>
                    )}
                  </div>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
      {list.length > 0 && (
        <div className="mt-8">
          <Pagination
            currentPage={page}
            totalPages={totalPages}
            onPageChange={setPage}
          />
        </div>
      )}
    </div>
  );
}
