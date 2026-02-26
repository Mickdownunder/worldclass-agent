import React, { useState } from "react";
import { Pagination } from "./Pagination";

export function BrainTab({ decisions, loading }: { decisions: any[] | null; loading: boolean }) {
  const [page, setPage] = useState(1);
  const itemsPerPage = 5; // Traces can contain multiple decisions, so 5 traces per page is enough

  if (loading) {
    return <div className="text-tron-dim p-4">Lade Decisions...</div>;
  }

  const grouped: Record<string, any[]> = {};
  const ungrouped: any[] = [];
  
  (decisions ?? []).forEach(d => {
    if (d.trace_id) {
      if (!grouped[d.trace_id]) grouped[d.trace_id] = [];
      grouped[d.trace_id].push(d);
    } else {
      ungrouped.push(d);
    }
  });

  const traceGroups = Object.entries(grouped);
  
  // Create an array of renderable items (trace groups + ungrouped items)
  const allItems: { type: 'trace' | 'single'; id: string; data: any }[] = [
    ...traceGroups.map(([traceId, traceDecisions]) => ({
      type: 'trace' as const,
      id: traceId,
      data: traceDecisions
    })),
    ...ungrouped.map((d, i) => ({
      type: 'single' as const,
      id: d.id ?? `ungrouped-${i}`,
      data: d
    }))
  ];

  const totalPages = Math.ceil(allItems.length / itemsPerPage);
  const displayedItems = allItems.slice((page - 1) * itemsPerPage, page * itemsPerPage);

  const renderDecision = (d: any, i: number) => {
    const phaseColors: Record<string, string> = {
      perceive: "var(--tron-info, #3b82f6)",
      think: "var(--tron-accent)",
      decide: "var(--tron-success)",
      act: "var(--tron-warning, #f59e0b)",
      reflect: "var(--tron-purple, #8b5cf6)",
    };
    const color = phaseColors[d.phase?.toLowerCase()] || "var(--tron-dim)";
    
    return (
      <li key={d.id ?? i} className="border-l-2 pl-3 pb-2" style={{ borderColor: `${color}40` }}>
        <div className="flex items-center gap-3 mb-1 flex-wrap">
          <span 
            className="rounded px-1.5 py-0.5 font-mono text-[10px] font-bold uppercase shrink-0" 
            style={{ background: "var(--tron-bg)", color }}
          >
            {d.phase}
          </span>
          <span className="text-tron-dim text-[11px] shrink-0">{d.ts}</span>
          <div className="flex items-center gap-1 ml-auto shrink-0">
            <span className="text-tron-muted text-[10px]">Conf:</span>
            <div className="h-1.5 w-12 bg-tron-border/50 rounded-full overflow-hidden">
              <div className="h-full bg-tron-accent rounded-full" style={{ width: `${Math.max(0, Math.min(100, (d.confidence ?? 0) * 100))}%` }}></div>
            </div>
          </div>
        </div>
        {d.reasoning != null && (
          <details className="mt-1 group cursor-pointer">
            <summary className="text-tron-text text-sm hover:text-tron-accent transition-colors select-none outline-none">
              {(d.reasoning as string).slice(0, 100)}
              {(d.reasoning as string).length > 100 ? "..." : ""}
              <span className="ml-2 text-tron-dim text-[10px] opacity-0 group-hover:opacity-100 transition-opacity">
                [Expand]
              </span>
            </summary>
            <p className="mt-2 text-tron-muted text-sm whitespace-pre-wrap pl-2 border-l border-tron-border/50">
              {d.reasoning}
            </p>
          </details>
        )}
      </li>
    );
  };
  
  return (
    <div className="tron-panel p-6">
      <h2 className="mb-4 text-lg font-medium text-tron-muted">Brain Cognitive Traces</h2>
      <p className="mb-3 text-[12px] text-tron-dim">Recent perceive → think → decide steps.</p>
      
      <div className="space-y-6">
        {displayedItems.map((item) => {
          if (item.type === 'trace') {
            return (
              <div key={item.id} className="border border-tron-border/30 rounded p-4 bg-tron-bg/30">
                <div className="text-xs font-mono text-tron-dim mb-3 pb-2 border-b border-tron-border/30">
                  Trace: {item.id.split('-')[0]}...
                </div>
                <ul className="space-y-4">
                  {item.data.map((d: any, i: number) => renderDecision(d, i))}
                </ul>
              </div>
            );
          } else {
            return (
              <ul key={item.id} className="space-y-4">
                {renderDecision(item.data, 0)}
              </ul>
            );
          }
        })}
      </div>

      {(decisions?.length ?? 0) === 0 && <p className="text-tron-dim">Noch keine Decisions.</p>}
      
      <Pagination currentPage={page} totalPages={totalPages} onPageChange={setPage} />
    </div>
  );
}
