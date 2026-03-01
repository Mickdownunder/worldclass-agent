import React, { useState } from "react";
import { Pagination } from "./Pagination";

const PHASE_META: Record<string, { icon: string; color: string }> = {
  perceive:   { icon: "👁", color: "#3b82f6" },
  understand: { icon: "🔍", color: "#06b6d4" },
  think:      { icon: "🧠", color: "#8b5cf6" },
  decide:     { icon: "⚡", color: "#f59e0b" },
  act:        { icon: "🚀", color: "#22c55e" },
  reflect:    { icon: "💡", color: "#ec4899" },
};

function ConfidenceRing({ value }: { value: number }) {
  const pct = Math.max(0, Math.min(100, value * 100));
  const r = 14;
  const circ = 2 * Math.PI * r;
  const offset = circ - (pct / 100) * circ;
  return (
    <svg width="36" height="36" viewBox="0 0 36 36">
      <circle cx="18" cy="18" r={r} fill="none" stroke="var(--tron-border, #1c2336)" strokeWidth="3" />
      <circle
        cx="18"
        cy="18"
        r={r}
        fill="none"
        stroke={pct >= 70 ? "#22c55e" : pct >= 40 ? "#f59e0b" : "#f43f5e"}
        strokeWidth="3"
        strokeLinecap="round"
        strokeDasharray={circ}
        strokeDashoffset={offset}
        transform="rotate(-90 18 18)"
      />
      <text x="18" y="19" textAnchor="middle" dominantBaseline="central" fontSize="9" fontWeight="700" fill="var(--tron-text, #fff)" fontFamily="monospace">
        {Math.round(pct)}
      </text>
    </svg>
  );
}

interface RetrievedMemoryIds {
  principle_ids?: string[];
  finding_ids?: string[];
  episode_ids?: string[];
}

interface MemoryDecision {
  id?: string;
  trace_id?: string;
  phase?: string;
  ts?: string;
  reasoning?: string;
  confidence?: number;
  metadata?: string | { retrieved_memory_ids?: RetrievedMemoryIds };
}

export function BrainTab({ decisions, loading }: { decisions: unknown[] | null; loading: boolean }) {
  const [page, setPage] = useState(1);
  const itemsPerPage = 5;

  if (loading) {
    return <div className="text-tron-dim p-4">Lade Cognitive Traces…</div>;
  }

  const grouped: Record<string, MemoryDecision[]> = {};
  const ungrouped: MemoryDecision[] = [];

  (decisions ?? []).forEach((d: unknown) => {
    const dec = d as MemoryDecision;
    if (dec.trace_id) {
      if (!grouped[dec.trace_id]) grouped[dec.trace_id] = [];
      grouped[dec.trace_id].push(dec);
    } else {
      ungrouped.push(dec);
    }
  });

  const traceGroups = Object.entries(grouped);

  const allItems: { type: "trace" | "single"; id: string; data: MemoryDecision | MemoryDecision[] }[] = [
    ...traceGroups.map(([traceId, traceDecisions]) => ({
      type: "trace" as const,
      id: traceId,
      data: traceDecisions,
    })),
    ...ungrouped.map((d, i) => ({
      type: "single" as const,
      id: d.id ?? `ungrouped-${i}`,
      data: d,
    })),
  ];

  const totalPages = Math.ceil(allItems.length / itemsPerPage);
  const displayedItems = allItems.slice((page - 1) * itemsPerPage, page * itemsPerPage);

  const getRetrievedIds = (d: MemoryDecision): RetrievedMemoryIds | null => {
    const raw = d.metadata;
    if (!raw) return null;
    const obj = typeof raw === "string" ? (() => { try { return JSON.parse(raw); } catch { return null; } })() : raw;
    return (obj?.retrieved_memory_ids as RetrievedMemoryIds) ?? null;
  };

  const renderDecision = (d: MemoryDecision, i: number) => {
    const meta = PHASE_META[d.phase?.toLowerCase() ?? ""] || { icon: "●", color: "var(--tron-dim)" };
    const ids = getRetrievedIds(d);

    return (
      <li key={d.id ?? i} className="relative pl-10 pb-4">
        {/* Timeline dot */}
        <div
          className="absolute left-0 top-0.5 w-7 h-7 rounded-full flex items-center justify-center text-sm"
          style={{
            background: `${meta.color}18`,
            border: `2px solid ${meta.color}60`,
          }}
        >
          {meta.icon}
        </div>

        <div className="flex items-start gap-3 flex-wrap">
          <span
            className="rounded px-2 py-0.5 font-mono text-[10px] font-bold uppercase shrink-0"
            style={{ background: `${meta.color}15`, color: meta.color, border: `1px solid ${meta.color}30` }}
          >
            {d.phase}
          </span>
          <span className="text-[10px] font-mono" style={{ color: "var(--tron-text-dim)" }}>{d.ts}</span>
          <div className="ml-auto shrink-0">
            <ConfidenceRing value={d.confidence ?? 0} />
          </div>
        </div>

        {ids && (ids.principle_ids?.length || ids.finding_ids?.length || ids.episode_ids?.length) ? (
          <div className="mt-2 flex items-center gap-2 text-[11px] p-2 rounded-lg bg-tron-bg-panel/50 border border-tron-border/30">
            <span className="text-tron-dim shrink-0 uppercase tracking-widest text-[9px] font-semibold">Basierend auf:</span>
            <div className="flex flex-wrap gap-1.5 flex-1">
              {ids.principle_ids?.slice(0, 5).map((pid) => (
                <button key={pid} onClick={() => { document.getElementById('tab-principles')?.click(); }} className="rounded-full px-2 py-0.5 font-mono text-[10px] text-[#c678ff] bg-[#c678ff]/10 border border-[#c678ff]/30 hover:bg-[#c678ff]/20 transition-colors shadow-[0_0_5px_rgba(198,120,255,0.2)]" title="Principle">P:{pid.slice(0, 8)}</button>
              ))}
              {ids.finding_ids?.slice(0, 5).map((fid) => (
                <button key={fid} onClick={() => { document.getElementById('tab-knowledge')?.click(); }} className="rounded-full px-2 py-0.5 font-mono text-[10px] text-tron-accent bg-tron-accent/10 border border-tron-accent/30 hover:bg-tron-accent/20 transition-colors shadow-[0_0_5px_rgba(0,212,255,0.2)]" title="Finding">F:{fid.slice(0, 8)}</button>
              ))}
              {ids.episode_ids?.slice(0, 3).map((eid) => (
                <button key={eid} onClick={() => { document.getElementById('tab-runs')?.click(); }} className="rounded-full px-2 py-0.5 font-mono text-[10px] text-tron-text bg-tron-text/10 border border-tron-text/30 hover:bg-tron-text/20 transition-colors shadow-[0_0_5px_rgba(255,255,255,0.1)]" title="Episode">E:{eid.slice(0, 8)}</button>
              ))}
            </div>
            <span className="text-[9px] text-tron-dim/50 ml-auto shrink-0 hidden sm:inline">(clickable)</span>
          </div>
        ) : null}

        {d.reasoning != null && (
          <details className="mt-2 group cursor-pointer">
            <summary className="text-sm hover:text-tron-accent transition-colors select-none outline-none" style={{ color: "var(--tron-text-muted)" }}>
              {(d.reasoning as string).slice(0, 140)}
              {(d.reasoning as string).length > 140 ? "…" : ""}
              <span className="ml-2 text-[10px] opacity-0 group-hover:opacity-100 transition-opacity" style={{ color: "var(--tron-text-dim)" }}>
                [Details]
              </span>
            </summary>
            <p className="mt-2 text-sm whitespace-pre-wrap pl-3 border-l-2" style={{ color: "var(--tron-text-muted)", borderColor: `${meta.color}30` }}>
              {d.reasoning}
            </p>
          </details>
        )}
      </li>
    );
  };

  return (
    <div className="tron-panel p-6">
      <h2 className="mb-1 text-lg font-medium" style={{ color: "var(--tron-text-muted)" }}>
        Cognitive Traces
      </h2>
      <p className="mb-4 text-[12px]" style={{ color: "var(--tron-text-dim)" }}>
        Jeder Trace = ein Cycle-Durchlauf (Perceive → Understand → Think → Decide → Act → Reflect). Bei Entscheidungen: angezeigte IDs = abgerufene Memories (Explainability).
      </p>

      <div className="space-y-6">
        {displayedItems.map((item) => {
          if (item.type === "trace") {
            return (
              <div
                key={item.id}
                className="rounded-lg p-4 relative"
                style={{
                  background: "var(--tron-bg)",
                  border: "1px solid var(--tron-border)",
                }}
              >
                <div className="flex items-center gap-2 mb-3 pb-2" style={{ borderBottom: "1px solid var(--tron-border)" }}>
                  <span className="text-[10px] font-mono" style={{ color: "var(--tron-text-dim)" }}>
                    Trace {item.id.slice(0, 8)}
                  </span>
                  {/* Mini flow indicator */}
                  <div className="flex items-center gap-0.5 ml-auto">
                    {(item.data as MemoryDecision[]).map((d: MemoryDecision, i: number) => {
                      const m = PHASE_META[d.phase?.toLowerCase() ?? ""] || { color: "var(--tron-dim)" };
                      return (
                        <React.Fragment key={i}>
                          <div
                            className="w-2 h-2 rounded-full"
                            style={{ background: m.color }}
                            title={d.phase}
                          />
                          {i < (item.data as MemoryDecision[]).length - 1 && (
                            <div className="w-3 h-px" style={{ background: "var(--tron-border)" }} />
                          )}
                        </React.Fragment>
                      );
                    })}
                  </div>
                </div>
                {/* Timeline connector line */}
                <div
                  className="absolute left-[2.15rem] top-[3.5rem] bottom-4 w-px"
                  style={{ background: "var(--tron-border)" }}
                />
                <ul className="space-y-3">
                  {(item.data as MemoryDecision[]).map((d: MemoryDecision, i: number) => renderDecision(d, i))}
                </ul>
              </div>
            );
          } else {
            return (
              <ul key={item.id} className="space-y-3">
                {renderDecision(item.data as MemoryDecision, 0)}
              </ul>
            );
          }
        })}
      </div>

      {(decisions?.length ?? 0) === 0 && (
        <p style={{ color: "var(--tron-text-dim)" }}>Noch keine Cognitive Traces. Starte einen Brain Cycle.</p>
      )}

      <Pagination currentPage={page} totalPages={totalPages} onPageChange={setPage} />
    </div>
  );
}
