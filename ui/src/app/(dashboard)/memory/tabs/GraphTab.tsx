"use client";

import { useState, useMemo, useCallback, useEffect, useRef } from "react";
import dynamic from 'next/dynamic';
import { useRouter } from "next/navigation";

// Only import client-side for Next.js to avoid SSR issues with WebGL
const ForceGraph3D = dynamic(() => import('react-force-graph-3d'), {
  ssr: false,
  loading: () => <div className="h-[500px] w-full flex flex-col items-center justify-center text-tron-dim border border-tron-border rounded-lg bg-tron-bg/50">
    <div className="w-8 h-8 border-2 border-tron-accent/30 border-t-tron-accent rounded-full animate-spin mb-4" />
    <p>Initializing 3D Neural Network...</p>
  </div>
});

interface ResearchProjectSummary {
  id: string;
  question?: string;
  status?: string;
  phase?: string;
  created_at?: string;
  parent_project_id?: string;
  has_master_dossier?: boolean;
}

export function GraphTab() {
  const router = useRouter();
  const [projects, setProjects] = useState<ResearchProjectSummary[]>([]);
  const [loading, setLoading] = useState(true);
  const graphRef = useRef<any>(null);

  useEffect(() => {
    setLoading(true);
    fetch("/api/research/projects")
      .then((r) => r.json())
      .then((d: { projects?: ResearchProjectSummary[] }) => {
        setProjects(d.projects ?? []);
      })
      .catch(() => setProjects([]))
      .finally(() => setLoading(false));
  }, []);

  const graphData = useMemo(() => {
    if (!projects.length) return { nodes: [], links: [] };
    
    const nodes = new Map<string, any>();
    const links: any[] = [];
    
    // Add all nodes
    projects.forEach((p) => {
      nodes.set(p.id, {
        id: p.id,
        name: p.question || p.id,
        status: p.status,
        hasMaster: p.has_master_dossier,
        isParent: !p.parent_project_id,
        val: !p.parent_project_id ? 10 : 5, // Parents are larger
        color: p.has_master_dossier 
          ? "#22c55e" // Emerald (Solved/Master)
          : !p.parent_project_id 
            ? "#00d4ff" // Cyan (Parent)
            : "#c678ff", // Purple (Follow-up)
      });
    });

    // Add links (Child -> Parent)
    projects.forEach((p) => {
      if (p.parent_project_id && nodes.has(p.parent_project_id)) {
        links.push({
          source: p.parent_project_id, // Parent
          target: p.id, // Child
          color: "rgba(0, 212, 255, 0.85)",
          value: 2
        });
      }
    });

    return { nodes: Array.from(nodes.values()), links };
  }, [projects]);

  useEffect(() => {
    const timer = setTimeout(() => {
      if (graphRef.current) {
        try {
          // Spread nodes a little wider so they don't clump
          graphRef.current.d3Force('charge').strength(-200);
        } catch (e) {}
      }
    }, 100);
    return () => clearTimeout(timer);
  }, [graphData]);

  const handleNodeClick = useCallback((node: any) => {
    if (node && node.id) {
      router.push(`/research/${node.id}`);
    }
  }, [router]);

  if (loading) {
    return (
      <div className="tron-panel p-6 flex items-center justify-center min-h-[500px]">
        <div className="text-tron-accent animate-pulse font-mono">SCANNING PROJECT MULTIVERSE...</div>
      </div>
    );
  }

  return (
    <div className="tron-panel p-0 overflow-hidden relative">
      <div className="absolute top-6 left-6 z-10 max-w-sm pointer-events-none">
        <h2 className="text-xl font-medium text-tron-text uppercase tracking-wider flex items-center gap-2">
          Project Lineage 
          <span className="text-[10px] bg-tron-accent/10 text-tron-accent px-2 py-0.5 rounded border border-tron-accent/30 font-mono">
            3D CLUSTER
          </span>
        </h2>
        <p className="text-sm text-tron-dim mt-2 bg-tron-bg/80 backdrop-blur-sm p-3 rounded-lg border border-tron-border/50">
          Global brain topology. Visualize how parent projects spawn recursive follow-up generations via the Research Council.
        </p>
        
        <div className="mt-4 flex flex-col gap-2 bg-tron-bg/80 backdrop-blur-sm p-3 rounded-lg border border-tron-border/50 text-xs font-mono">
          <div className="flex items-center gap-3">
            <div className="w-3 h-3 rounded-full" style={{ background: "var(--tron-accent)", boxShadow: "0 0 8px var(--tron-accent)" }} />
            <span className="text-tron-text">Parent Project (Root)</span>
          </div>
          <div className="flex items-center gap-3">
            <div className="w-3 h-3 rounded-full" style={{ background: "#c678ff", boxShadow: "0 0 8px #c678ff" }} />
            <span className="text-tron-text">Council Follow-up (Child)</span>
          </div>
          <div className="flex items-center gap-3">
            <div className="w-3 h-3 rounded-full" style={{ background: "#22c55e", boxShadow: "0 0 8px #22c55e" }} />
            <span className="text-tron-text">Solved (Master Dossier)</span>
          </div>
        </div>
        
        <div className="mt-4 text-[10px] text-tron-dim italic">
          Tip: Left-Click & Drag to rotate • Scroll to zoom • Click node to open
        </div>
      </div>

      {!graphData.nodes.length ? (
        <div className="flex items-center justify-center min-h-[600px] text-tron-dim">
          No projects found in the system yet.
        </div>
      ) : (
        <div className="w-full relative" style={{ height: "calc(100vh - 200px)", minHeight: "600px", background: "#050814" }}>
          <ForceGraph3D
            ref={graphRef}
            graphData={graphData}
            nodeLabel={(node: any) => `<div style="color: white; background: rgba(0,0,0,0.8); padding: 4px; border-radius: 4px; border: 1px solid ${node.color}">${node.name}</div>`}
            nodeColor="color"
            nodeVal="val"
            linkColor="color"
            linkWidth={2}
            linkDirectionalParticles={2}
            linkDirectionalParticleSpeed={0.005}
            linkDirectionalParticleColor={() => "#00d4ff"}
            backgroundColor="#050814"
            onNodeClick={handleNodeClick}
            nodeResolution={16}
            controlType="trackball"
            showNavInfo={false}
            enableNodeDrag={true}
          />
        </div>
      )}
    </div>
  );
}
