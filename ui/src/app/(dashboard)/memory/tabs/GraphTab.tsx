"use client";

import { useState, useMemo, useCallback } from "react";
import { Pagination } from "./Pagination";
import dynamic from 'next/dynamic';

const ForceGraph2D = dynamic(() => import('react-force-graph-2d'), {
  ssr: false,
  loading: () => <div className="h-[400px] w-full flex items-center justify-center text-tron-dim border border-tron-border rounded-lg bg-tron-bg/50">Loading Network Graph...</div>
});

export function GraphTab({ edges, loading }: { edges: any[] | null; loading: boolean }) {
  const [page, setPage] = useState(1);
  const itemsPerPage = 10;
  const [viewMode, setViewMode] = useState<"visual" | "list">("visual");

  const list = Array.isArray(edges) ? edges : [];
  
  // Transform data for force graph
  const graphData = useMemo(() => {
    if (!list.length) return { nodes: [], links: [] };
    
    const nodes = new Map();
    const links = [];
    
    list.forEach(edge => {
      // Add Strategy Node
      if (!nodes.has(edge.from_node_id)) {
        nodes.set(edge.from_node_id, {
          id: edge.from_node_id,
          name: edge.strategy_name || `Strategy ${edge.from_node_id.slice(0, 4)}`,
          val: 8, // node size
          color: "var(--tron-accent)", // Cyan
          type: "strategy"
        });
      }
      
      // Add Episode Node
      if (!nodes.has(edge.to_node_id)) {
        nodes.set(edge.to_node_id, {
          id: edge.to_node_id,
          name: `Run ${edge.project_id?.slice(0, 8) || ''}`,
          val: 4, // smaller
          color: "#c678ff", // Magenta
          type: "episode"
        });
      }
      
      // Add Link
      links.push({
        source: edge.from_node_id,
        target: edge.to_node_id,
        color: "rgba(0, 212, 255, 0.2)"
      });
    });
    
    return {
      nodes: Array.from(nodes.values()),
      links
    };
  }, [list]);

  // Group edges by from_node_id (e.g. strategy) for list view
  const groupedEdges = list.reduce((acc: any, edge: any) => {
    if (!acc[edge.from_node_id]) {
      acc[edge.from_node_id] = [];
    }
    acc[edge.from_node_id].push(edge);
    return acc;
  }, {});

  const entries = Object.entries(groupedEdges);
  const totalPages = Math.ceil(entries.length / itemsPerPage) || 1;
  const slice = entries.slice((page - 1) * itemsPerPage, page * itemsPerPage);

  const drawNode = useCallback((node: any, ctx: any, globalScale: any) => {
    const label = node.name;
    const fontSize = 12/globalScale;
    ctx.font = `${fontSize}px Sans-Serif`;
    
    // Draw circle
    ctx.beginPath();
    ctx.arc(node.x, node.y, node.val, 0, 2 * Math.PI, false);
    ctx.fillStyle = node.color;
    
    // Add glow
    ctx.shadowColor = node.color;
    ctx.shadowBlur = 10;
    ctx.fill();
    
    // Reset shadow for text
    ctx.shadowBlur = 0;
    
    // Only draw label if zoomed in or node is large
    if (globalScale > 1.5 || node.val > 5) {
      ctx.textAlign = 'center';
      ctx.textBaseline = 'middle';
      ctx.fillStyle = 'rgba(255, 255, 255, 0.8)';
      ctx.fillText(label, node.x, node.y + node.val + (fontSize));
    }
  }, []);

  if (loading) {
    return <div className="text-tron-dim p-6">Lade Graph-Kanten…</div>;
  }

  return (
    <div className="tron-panel p-6">
      <div className="flex justify-between items-start mb-6">
        <div>
          <h2 className="text-lg font-medium text-tron-muted">Strategy-Episode Network</h2>
          <p className="text-sm text-tron-dim mt-1">
            Visualisierung: Welche Strategies (Nodes) in welchen Episoden/Runs genutzt wurden.
          </p>
        </div>
        <div className="flex gap-1 bg-tron-bg p-1 rounded-md border border-tron-border/50">
          <button 
            onClick={() => setViewMode("visual")}
            className={`px-3 py-1.5 text-xs rounded transition-colors ${viewMode === 'visual' ? 'bg-tron-accent/20 text-tron-accent border border-tron-accent/30' : 'text-tron-dim hover:text-tron-text'}`}
          >
            Network
          </button>
          <button 
            onClick={() => setViewMode("list")}
            className={`px-3 py-1.5 text-xs rounded transition-colors ${viewMode === 'list' ? 'bg-tron-accent/20 text-tron-accent border border-tron-accent/30' : 'text-tron-dim hover:text-tron-text'}`}
          >
            List
          </button>
        </div>
      </div>

      {entries.length === 0 ? (
        <p className="text-tron-dim">Noch keine Graph-Daten.</p>
      ) : viewMode === "visual" ? (
        <div className="border border-tron-border/60 rounded-xl overflow-hidden bg-tron-bg-panel/80 relative" style={{ height: "500px" }}>
          <div className="absolute top-4 left-4 z-10 flex flex-col gap-2 bg-tron-bg/80 backdrop-blur p-3 rounded-lg border border-tron-border/50 text-xs">
            <div className="flex items-center gap-2">
              <div className="w-3 h-3 rounded-full" style={{ background: "var(--tron-accent)", boxShadow: "0 0 8px var(--tron-accent)" }}></div>
              <span className="text-tron-text">Strategy</span>
            </div>
            <div className="flex items-center gap-2">
              <div className="w-3 h-3 rounded-full" style={{ background: "#c678ff", boxShadow: "0 0 8px #c678ff" }}></div>
              <span className="text-tron-text">Episode (Run)</span>
            </div>
          </div>
          
          <ForceGraph2D
            graphData={graphData}
            nodeCanvasObject={drawNode}
            linkColor="color"
            linkWidth={1}
            nodeRelSize={6}
            backgroundColor="transparent"
            cooldownTicks={100}
            d3AlphaDecay={0.02}
            d3VelocityDecay={0.3}
          />
        </div>
      ) : (
        <div className="space-y-4">
          {slice.map(([fromId, nodeEdges]: any) => {
            const first = nodeEdges[0];
            const strategyName = first?.strategy_name;
            const strategyDomain = first?.strategy_domain;
            return (
              <div key={fromId} className="border border-tron-border/60 rounded-xl p-5 text-sm bg-tron-bg-panel/50 hover:border-tron-accent/40 transition-colors">
                <div className="flex flex-wrap items-center gap-3 mb-4 border-b border-tron-border/30 pb-3">
                  <div className="w-2.5 h-2.5 rounded-full" style={{ background: "var(--tron-accent)", boxShadow: "0 0 8px var(--tron-accent)" }}></div>
                  <span className="text-tron-muted font-bold tracking-wider text-[11px] uppercase">
                    Strategy
                  </span>
                  {strategyName ? (
                    <>
                      <span className="font-semibold text-tron-accent">{strategyName}</span>
                      {strategyDomain && (
                        <span className="text-[10px] px-2 py-0.5 rounded-full bg-tron-bg border border-tron-border text-tron-dim">
                          {strategyDomain}
                        </span>
                      )}
                    </>
                  ) : (
                    <span className="font-mono text-xs px-2 py-0.5 rounded bg-tron-bg border border-tron-border text-tron-text">
                      {fromId.slice(0, 16)}…
                    </span>
                  )}
                  <span className="text-tron-dim text-[11px] ml-auto border border-tron-border/50 px-2 py-0.5 rounded bg-tron-bg">
                    {nodeEdges.length} Episodes
                  </span>
                </div>
                <div className="pl-6 space-y-3 relative">
                  <div className="absolute left-[11px] top-2 bottom-2 w-px bg-tron-border/50"></div>
                  {nodeEdges.map((e: any, i: number) => (
                    <div key={i} className="flex flex-wrap items-center gap-3 text-xs relative">
                      <div className="absolute -left-[14.5px] top-1/2 -translate-y-1/2 w-1.5 h-1.5 rounded-full" style={{ background: "#c678ff", boxShadow: "0 0 5px #c678ff" }}></div>
                      <span className="text-tron-dim uppercase text-[10px] tracking-wider w-16">Episode</span>
                      <span className="font-mono text-tron-text bg-tron-bg px-1.5 py-0.5 rounded border border-tron-border/30" title={e.to_node_id}>
                        {(e.to_node_id || "").slice(0, 12)}…
                      </span>
                      {e.project_id && (
                        <span className="text-tron-dim font-mono text-[10px] ml-2" title={e.project_id}>
                          Proj: {e.project_id}
                        </span>
                      )}
                    </div>
                  ))}
                </div>
              </div>
            );
          })}
        </div>
      )}

      {viewMode === "list" && entries.length > 0 && (
        <div className="mt-6">
          <Pagination currentPage={page} totalPages={totalPages} onPageChange={setPage} />
        </div>
      )}
    </div>
  );
}
