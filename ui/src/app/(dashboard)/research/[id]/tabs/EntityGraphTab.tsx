"use client";

import { useState, useEffect, useMemo, useCallback } from "react";
import dynamic from "next/dynamic";

const ForceGraph2D = dynamic(() => import("react-force-graph-2d"), {
  ssr: false,
  loading: () => (
    <div className="h-[400px] w-full flex items-center justify-center text-tron-dim border border-tron-border rounded-lg bg-tron-bg/50">
      Loading Knowledge Map...
    </div>
  ),
});

interface EntityGraphData {
  entities: { id?: string; name?: string; type?: string }[];
  relations: { from?: string; to?: string; relation_type?: string }[];
}

export function EntityGraphTab({ projectId }: { projectId: string }) {
  const [data, setData] = useState<EntityGraphData | null | "loading">("loading");
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    fetch(`/api/research/projects/${encodeURIComponent(projectId)}/entity-graph`)
      .then((r) => {
        if (!r.ok) {
          if (r.status === 404) throw new Error("No Entity Graph found (Connect phase not executed yet).");
          throw new Error(r.statusText || "Error loading graph.");
        }
        return r.json();
      })
      .then((d: EntityGraphData) => {
        setData(d);
        setError(null);
      })
      .catch((e: Error) => {
        setData(null);
        setError(e.message || "Unknown error");
      });
  }, [projectId]);

  const graphData = useMemo(() => {
    if (!data || data === "loading" || !data.entities?.length) return { nodes: [], links: [] };
    const nodes = new Map<string, { id: string; name: string; val: number; color: string; type: string }>();
    data.entities.forEach((e) => {
      const id = (e.name ?? e.id ?? "").trim() || String(e.id ?? "");
      if (!id) return;
      if (!nodes.has(id)) {
        nodes.set(id, {
          id,
          name: (e.name ?? e.id ?? id).slice(0, 40),
          val: 6,
          color: "var(--tron-accent)", // Neon blue/cyan
          type: (e.type as string) || "entity",
        });
      }
    });
    const links: { source: string; target: string; color: string }[] = [];
    (data.relations ?? []).forEach((r) => {
      const from = (r.from ?? "").trim();
      const to = (r.to ?? "").trim();
      if (from && to && nodes.has(from) && nodes.has(to)) {
        links.push({ source: from, target: to, color: "rgba(0, 212, 255, 0.4)" });
      }
    });
    return { nodes: Array.from(nodes.values()), links };
  }, [data]);

  const drawNode = useCallback((node: any, ctx: any, globalScale: any) => {
    const label = node.name;
    const fontSize = 12 / globalScale;
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
    if (globalScale > 1.2 || node.val > 5) {
      ctx.textAlign = "center";
      ctx.textBaseline = "middle";
      ctx.fillStyle = "rgba(255, 255, 255, 0.9)";
      ctx.fillText(label, node.x, node.y + node.val + fontSize);
    }
  }, []);

  if (data === "loading") {
    return <div className="text-tron-dim p-4">Loading Knowledge Map...</div>;
  }

  if (error) {
    return <div className="text-amber-400 p-4">{error}</div>;
  }

  if (!data || !data.entities?.length) {
    return <div className="text-tron-dim p-4">No Knowledge Map data available for this project yet.</div>;
  }

  return (
    <div className="space-y-4">
      <div className="flex justify-between items-center mb-2 px-2">
        <div>
          <h3 className="text-sm font-semibold text-tron-text uppercase tracking-wider">Knowledge Map</h3>
          <p className="text-[11px] text-tron-dim">
            Extracted entities and relationships from the Connect phase.
          </p>
        </div>
        <div className="flex items-center gap-2 text-[10px]">
          <span className="font-mono text-tron-accent">{graphData.nodes.length} Nodes</span>
          <span className="text-tron-dim">|</span>
          <span className="font-mono text-tron-accent">{graphData.links.length} Relations</span>
        </div>
      </div>
      
      <div
        className="border border-tron-border/60 rounded-xl overflow-hidden bg-tron-bg-panel/80 relative"
        style={{ height: "600px" }}
      >
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
    </div>
  );
}
