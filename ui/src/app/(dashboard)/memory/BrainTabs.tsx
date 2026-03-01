"use client";

import { useState, useEffect } from "react";
import type { MemorySummary } from "@/lib/operator/memory";
import { ActivityTab } from "./tabs/ActivityTab";
import { PrinciplesTab } from "./tabs/PrinciplesTab";
import { SourcesTab } from "./tabs/SourcesTab";
import { BrainTab } from "./tabs/BrainTab";
import { KnowledgeTab } from "./tabs/KnowledgeTab";
import { PlumberTab } from "./tabs/PlumberTab";
import { RunsTab } from "./tabs/RunsTab";
import { StrategiesTab } from "./tabs/StrategiesTab";
import { UtilityTab } from "./tabs/UtilityTab";
import { GraphTab } from "./tabs/GraphTab";

type TabId = "activity" | "runs" | "strategies" | "principles" | "sources" | "brain" | "utility" | "graph" | "plumber" | "knowledge";

export function BrainTabs({ memorySummary }: { memorySummary: MemorySummary | null }) {
  const [activeTab, setActiveTab] = useState<TabId>("activity");

  const [principles, setPrinciples] = useState<unknown[] | null>(null);
  const [strategies, setStrategies] = useState<unknown[] | null>(null);
  const [utility, setUtility] = useState<unknown[] | null>(null);
  const [graphEdges, setGraphEdges] = useState<unknown[] | null>(null);
  const [credibility, setCredibility] = useState<unknown[] | null>(null);
  const [decisions, setDecisions] = useState<unknown[] | null>(null);
  const [entities, setEntities] = useState<unknown[] | null>(null);
  const [outcomes, setOutcomes] = useState<unknown[] | null>(null);
  
  const [loading, setLoading] = useState<Record<TabId, boolean>>({
    activity: false,
    runs: false,
    strategies: false,
    principles: false,
    sources: false,
    brain: false,
    utility: false,
    graph: false,
    plumber: false,
    knowledge: false,
  });

  useEffect(() => {
    /* eslint-disable react-hooks/set-state-in-effect -- lazy-load per tab: set loading then fetch */
    if (activeTab === "strategies" && strategies === null) {
      setLoading((l) => ({ ...l, strategies: true }));
      fetch("/api/memory/strategies")
        .then((r) => r.json())
        .then((d) => setStrategies((d as { strategies?: unknown[] }).strategies ?? (d as unknown[]) ?? []))
        .catch(() => setStrategies([]))
        .finally(() => setLoading((l) => ({ ...l, strategies: false })));
    }
    if (activeTab === "utility" && utility === null) {
      setLoading((l) => ({ ...l, utility: true }));
      fetch("/api/memory/utility")
        .then((r) => r.json())
        .then((d) => setUtility((d as { utility?: unknown[] }).utility ?? (d as unknown[]) ?? []))
        .catch(() => setUtility([]))
        .finally(() => setLoading((l) => ({ ...l, utility: false })));
    }
    if (activeTab === "graph" && graphEdges === null) {
      setLoading((l) => ({ ...l, graph: true }));
      fetch("/api/memory/graph")
        .then((r) => r.json())
        .then((d) => setGraphEdges((d as { edges?: unknown[] }).edges ?? (d as unknown[]) ?? []))
        .catch(() => setGraphEdges([]))
        .finally(() => setLoading((l) => ({ ...l, graph: false })));
    }
    if (activeTab === "principles" && principles === null) {
      setLoading((l) => ({ ...l, principles: true }));
      fetch("/api/memory/principles")
        .then((r) => r.json())
        .then((d) => setPrinciples((d as { principles?: unknown[] }).principles ?? (d as unknown[]) ?? []))
        .catch(() => setPrinciples([]))
        .finally(() => setLoading((l) => ({ ...l, principles: false })));
    }
    if (activeTab === "sources" && credibility === null) {
      setLoading((l) => ({ ...l, sources: true }));
      fetch("/api/memory/credibility")
        .then((r) => r.json())
        .then((d) => setCredibility((d as { credibility?: unknown[] }).credibility ?? (d as unknown[]) ?? []))
        .catch(() => setCredibility([]))
        .finally(() => setLoading((l) => ({ ...l, sources: false })));
    }
    if (activeTab === "brain" && decisions === null) {
      setLoading((l) => ({ ...l, brain: true }));
      fetch("/api/memory/decisions")
        .then((r) => r.json())
        .then((d) => setDecisions((d as { decisions?: unknown[] }).decisions ?? (d as unknown[]) ?? []))
        .catch(() => setDecisions([]))
        .finally(() => setLoading((l) => ({ ...l, brain: false })));
    }
    if (activeTab === "knowledge" && (entities === null || outcomes === null)) {
      setLoading((l) => ({ ...l, knowledge: true }));
      Promise.all([
        fetch("/api/memory/entities").then((r) => r.json()),
        fetch("/api/memory/outcomes").then((r) => r.json()),
      ])
        .then(([entData, outData]) => {
          setEntities((entData as { entities?: unknown[] }).entities ?? (entData as unknown[]) ?? []);
          setOutcomes((outData as { outcomes?: unknown[] }).outcomes ?? (outData as unknown[]) ?? []);
        })
        .catch(() => {
          setEntities([]);
          setOutcomes([]);
        })
        .finally(() => setLoading((l) => ({ ...l, knowledge: false })));
    }
    /* eslint-enable react-hooks/set-state-in-effect */
  }, [activeTab, strategies, utility, graphEdges, principles, credibility, decisions, entities, outcomes]);

  const tabs: { id: TabId; label: string }[] = [
    { id: "activity", label: "Activity" },
    { id: "runs", label: "Run Timeline" },
    { id: "graph", label: "Network Graph" },
    { id: "utility", label: "Utility Ranking" },
    { id: "strategies", label: "Strategies" },
    { id: "principles", label: "Principles" },
    { id: "sources", label: "Sources" },
    { id: "brain", label: "Cognitive Traces" },
    { id: "knowledge", label: "Knowledge Base" },
    { id: "plumber", label: "🔧 Plumber" },
  ];

  const { recent_episodes = [], recent_reflections = [], recent_run_episodes = [], playbooks = [] } = memorySummary ?? {};

  return (
    <div className="space-y-0 mt-6">
      <div
        className="flex items-end gap-px px-0 overflow-x-auto"
        style={{ borderBottom: "1px solid var(--tron-border)" }}
      >
        {tabs.map((t) => (
          <button
            key={t.id}
            id={`tab-${t.id}`}
            type="button"
            onClick={() => setActiveTab(t.id)}
            className="relative shrink-0 px-4 py-2.5 text-[12px] font-semibold uppercase tracking-wider transition-colors"
            style={{
              color: activeTab === t.id ? "var(--tron-accent)" : "var(--tron-text-muted)",
              background: "transparent",
              borderBottom: activeTab === t.id ? "2px solid var(--tron-accent)" : "2px solid transparent",
              marginBottom: "-1px",
            }}
          >
            {t.label}
          </button>
        ))}
      </div>

      <div className="pt-6">
        {activeTab === "activity" && (
          <ActivityTab
            episodes={recent_episodes}
            reflections={recent_reflections}
            consolidation={memorySummary?.consolidation}
          />
        )}
        {activeTab === "runs" && (
          <RunsTab runs={recent_run_episodes} />
        )}
        {activeTab === "strategies" && (
          <StrategiesTab strategies={strategies} loading={loading.strategies} />
        )}
        {activeTab === "principles" && (
          <PrinciplesTab principles={principles} loading={loading.principles} />
        )}
        {activeTab === "sources" && (
          <SourcesTab credibility={credibility} loading={loading.sources} />
        )}
        {activeTab === "brain" && (
          <BrainTab decisions={decisions} loading={loading.brain} />
        )}
        {activeTab === "utility" && (
          <UtilityTab utility={utility} loading={loading.utility} />
        )}
        {activeTab === "graph" && (
          <GraphTab edges={graphEdges} loading={loading.graph} />
        )}
        {activeTab === "plumber" && <PlumberTab />}
        {activeTab === "knowledge" && (
          <KnowledgeTab
            entities={entities}
            playbooks={playbooks}
            outcomes={outcomes}
            loading={{ entities: loading.knowledge, outcomes: loading.knowledge }}
          />
        )}
      </div>
    </div>
  );
}
