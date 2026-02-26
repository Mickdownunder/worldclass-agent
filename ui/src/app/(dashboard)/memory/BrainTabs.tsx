"use client";

import { useState, useEffect } from "react";
import { ActivityTab } from "./tabs/ActivityTab";
import { PrinciplesTab } from "./tabs/PrinciplesTab";
import { SourcesTab } from "./tabs/SourcesTab";
import { BrainTab } from "./tabs/BrainTab";
import { KnowledgeTab } from "./tabs/KnowledgeTab";

type TabId = "activity" | "principles" | "sources" | "brain" | "knowledge";

export function BrainTabs({ memorySummary }: { memorySummary: any }) {
  const [activeTab, setActiveTab] = useState<TabId>("activity");
  
  const [principles, setPrinciples] = useState<any[] | null>(null);
  const [credibility, setCredibility] = useState<any[] | null>(null);
  const [decisions, setDecisions] = useState<any[] | null>(null);
  const [entities, setEntities] = useState<any[] | null>(null);
  const [outcomes, setOutcomes] = useState<any[] | null>(null);
  
  const [loading, setLoading] = useState<Record<TabId, boolean>>({
    activity: false,
    principles: false,
    sources: false,
    brain: false,
    knowledge: false,
  });

  useEffect(() => {
    if (activeTab === "principles" && principles === null) {
      setLoading((l) => ({ ...l, principles: true }));
      fetch("/api/memory/principles")
        .then((r) => r.json())
        .then((d) => setPrinciples(d.principles ?? d ?? []))
        .catch(() => setPrinciples([]))
        .finally(() => setLoading((l) => ({ ...l, principles: false })));
    }
    if (activeTab === "sources" && credibility === null) {
      setLoading((l) => ({ ...l, sources: true }));
      fetch("/api/memory/credibility")
        .then((r) => r.json())
        .then((d) => setCredibility(d.credibility ?? d ?? []))
        .catch(() => setCredibility([]))
        .finally(() => setLoading((l) => ({ ...l, sources: false })));
    }
    if (activeTab === "brain" && decisions === null) {
      setLoading((l) => ({ ...l, brain: true }));
      fetch("/api/memory/decisions")
        .then((r) => r.json())
        .then((d) => setDecisions(d.decisions ?? d ?? []))
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
          setEntities(entData.entities ?? entData ?? []);
          setOutcomes(outData.outcomes ?? outData ?? []);
        })
        .catch(() => {
          setEntities([]);
          setOutcomes([]);
        })
        .finally(() => setLoading((l) => ({ ...l, knowledge: false })));
    }
  }, [activeTab, principles, credibility, decisions, entities, outcomes]);

  const tabs: { id: TabId; label: string }[] = [
    { id: "activity", label: "Activity" },
    { id: "principles", label: "Principles" },
    { id: "sources", label: "Sources" },
    { id: "brain", label: "Brain" },
    { id: "knowledge", label: "Knowledge" },
  ];

  const { recent_episodes, recent_reflections, playbooks } = memorySummary ?? {};

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
            episodes={recent_episodes ?? []}
            reflections={recent_reflections ?? []}
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
        {activeTab === "knowledge" && (
          <KnowledgeTab
            entities={entities}
            playbooks={playbooks ?? []}
            outcomes={outcomes}
            loading={{ entities: loading.knowledge, outcomes: loading.knowledge }}
          />
        )}
      </div>
    </div>
  );
}
