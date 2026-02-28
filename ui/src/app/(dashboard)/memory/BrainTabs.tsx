"use client";

import { useState, useEffect } from "react";
import type { MemorySummary } from "@/lib/operator/memory";
import { ActivityTab } from "./tabs/ActivityTab";
import { PrinciplesTab } from "./tabs/PrinciplesTab";
import { SourcesTab } from "./tabs/SourcesTab";
import { BrainTab } from "./tabs/BrainTab";
import { KnowledgeTab } from "./tabs/KnowledgeTab";
import { PlumberTab } from "./tabs/PlumberTab";

type TabId = "activity" | "principles" | "sources" | "brain" | "plumber" | "knowledge";

export function BrainTabs({ memorySummary }: { memorySummary: MemorySummary | null }) {
  const [activeTab, setActiveTab] = useState<TabId>("activity");

  const [principles, setPrinciples] = useState<unknown[] | null>(null);
  const [credibility, setCredibility] = useState<unknown[] | null>(null);
  const [decisions, setDecisions] = useState<unknown[] | null>(null);
  const [entities, setEntities] = useState<unknown[] | null>(null);
  const [outcomes, setOutcomes] = useState<unknown[] | null>(null);
  
  const [loading, setLoading] = useState<Record<TabId, boolean>>({
    activity: false,
    principles: false,
    sources: false,
    brain: false,
    plumber: false,
    knowledge: false,
  });

  useEffect(() => {
    /* eslint-disable react-hooks/set-state-in-effect -- lazy-load per tab: set loading then fetch */
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
  }, [activeTab, principles, credibility, decisions, entities, outcomes]);

  const tabs: { id: TabId; label: string }[] = [
    { id: "activity", label: "Activity" },
    { id: "principles", label: "Principles" },
    { id: "sources", label: "Sources" },
    { id: "brain", label: "Brain" },
    { id: "plumber", label: "🔧 Plumber" },
    { id: "knowledge", label: "Knowledge" },
  ];

  const { recent_episodes = [], recent_reflections = [], playbooks = [] } = memorySummary ?? {};

  return (
    <div className="space-y-0 mt-6">
      <div
        className="flex items-end gap-px px-0 overflow-x-auto"
        style={{ borderBottom: "1px solid var(--tron-border)" }}
      >
        {tabs.map((t) => (
          <button
            key={t.id}
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
          />
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
