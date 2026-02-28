import React, { useState } from "react";
import Link from "next/link";
import { Pagination } from "./Pagination";

interface EntityRow {
  id?: string;
  name?: string;
  type?: string;
  first_seen_project?: string;
}
interface PlaybookRow {
  domain: string;
  strategy: string;
  success_rate: number;
}
interface OutcomeRow {
  project_id?: string;
  domain?: string;
  critic_score?: number;
  user_verdict?: string;
}

export function KnowledgeTab({ 
  entities, 
  playbooks, 
  outcomes, 
  loading 
}: {
  entities: unknown[] | null;
  playbooks: PlaybookRow[];
  outcomes: unknown[] | null;
  loading: { entities: boolean; outcomes: boolean };
}) {
  const [entityPage, setEntityPage] = useState(1);
  const [outcomePage, setOutcomePage] = useState(1);
  const [playbookPage, setPlaybookPage] = useState(1);
  
  const entitiesPerPage = 10;
  const outcomesPerPage = 10;
  const playbooksPerPage = 10;

  const allEntities = entities ?? [];
  const allOutcomes = outcomes ?? [];
  const allPlaybooks = playbooks ?? [];

  const entityTotalPages = Math.ceil(allEntities.length / entitiesPerPage);
  const outcomeTotalPages = Math.ceil(allOutcomes.length / outcomesPerPage);
  const playbookTotalPages = Math.ceil(allPlaybooks.length / playbooksPerPage);

  const displayedEntities = allEntities.slice((entityPage - 1) * entitiesPerPage, entityPage * entitiesPerPage);
  const displayedOutcomes = allOutcomes.slice((outcomePage - 1) * outcomesPerPage, outcomePage * outcomesPerPage);
  const displayedPlaybooks = allPlaybooks.slice((playbookPage - 1) * playbooksPerPage, playbookPage * playbooksPerPage);

  return (
    <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
      {/* Left: Entities */}
      <div className="tron-panel p-6 flex flex-col">
        <h2 className="mb-4 text-lg font-medium text-tron-muted">Entities</h2>
        {loading.entities ? (
          <div className="text-tron-dim text-sm">Lade Entities...</div>
        ) : (
          <>
            <div className="overflow-x-auto flex-1">
              <table className="w-full text-[12px] data-table">
                <thead>
                  <tr className="text-left text-tron-dim border-b border-tron-border">
                    <th className="pb-2 pr-4">Name</th>
                    <th className="pb-2 pr-4">Type</th>
                    <th className="pb-2">First seen</th>
                  </tr>
                </thead>
                <tbody>
                  {displayedEntities.map((e, i) => {
                    const row = e as EntityRow;
                    return (
                      <tr key={row.id ?? i} className="border-b border-tron-border/50 interactive-row">
                        <td className="py-2 pr-4 font-mono text-tron-text">{row.name ?? "—"}</td>
                        <td className="py-2 pr-4 text-tron-muted">{row.type ?? "—"}</td>
                        <td className="py-2 text-tron-dim">{row.first_seen_project ?? "—"}</td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
              {allEntities.length === 0 && <p className="text-tron-dim mt-2">Noch keine Entities.</p>}
            </div>
            <div className="mt-auto">
              <Pagination currentPage={entityPage} totalPages={entityTotalPages} onPageChange={setEntityPage} />
            </div>
          </>
        )}
      </div>

      {/* Right: Playbooks & Outcomes */}
      <div className="flex flex-col gap-6">
        {/* Playbooks */}
        <div className="tron-panel p-6 flex flex-col">
          <h2 className="mb-4 text-lg font-medium text-tron-muted">Angewandte Playbooks</h2>
          <div className="flex-1">
            <ul className="space-y-3">
              {displayedPlaybooks.map((p, i) => (
                <li key={i} className="text-sm border-l-2 border-tron-accent/30 pl-3">
                  <span className="text-tron-accent font-medium">{p.domain}</span>
                  <span className="mx-2 text-tron-dim">·</span>
                  <span className="text-tron-text">{p.strategy}</span>
                  <span className="ml-2 text-tron-muted">({(p.success_rate * 100).toFixed(0)}%)</span>
                </li>
              ))}
            </ul>
            {allPlaybooks.length === 0 && (
              <p className="text-tron-dim text-sm">Noch keine Playbooks.</p>
            )}
          </div>
          <div className="mt-auto">
            <Pagination currentPage={playbookPage} totalPages={playbookTotalPages} onPageChange={setPlaybookPage} />
          </div>
        </div>

        {/* Outcomes */}
        <div className="tron-panel p-6 flex flex-col">
          <h2 className="mb-4 text-lg font-medium text-tron-muted">Project Outcomes</h2>
          {loading.outcomes ? (
            <div className="text-tron-dim text-sm">Lade Outcomes...</div>
          ) : (
            <>
              <div className="flex-1">
                <ul className="space-y-2">
                  {displayedOutcomes.map((o, i) => {
                    const out = o as OutcomeRow;
                    return (
                      <li key={i} className="flex flex-wrap items-center gap-2 text-sm border-b border-tron-border/30 pb-2 last:border-0 last:pb-0">
                        <Link href={`/research/${out.project_id ?? ""}`} className="font-mono text-tron-accent hover:underline">
                          {out.project_id ?? "—"}
                        </Link>
                        <span className="text-tron-dim text-[11px]">{out.domain ?? ""}</span>
                        <span className="text-tron-muted text-[11px]">critic: {(out.critic_score ?? 0).toFixed(2)}</span>
                        <span
                          className="rounded px-1.5 py-0.5 text-[10px] font-bold"
                          style={{
                            background: "var(--tron-bg)",
                            color: out.user_verdict === "accepted" ? "var(--tron-success)" : out.user_verdict === "rejected" ? "var(--tron-error)" : "var(--tron-text-muted)",
                          }}
                        >
                          {out.user_verdict ?? "—"}
                        </span>
                      </li>
                    );
                  })}
                </ul>
                {allOutcomes.length === 0 && <p className="text-tron-dim text-sm mt-2">Noch keine Outcomes.</p>}
              </div>
              <div className="mt-auto">
                <Pagination currentPage={outcomePage} totalPages={outcomeTotalPages} onPageChange={setOutcomePage} />
              </div>
            </>
          )}
        </div>
      </div>
    </div>
  );
}
