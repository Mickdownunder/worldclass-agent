import { getMemorySummary, getDecisions } from "@/lib/operator/memory";
import { getHealth } from "@/lib/operator/health";
import { BrainTabs } from "./BrainTabs";
import { BrainRiverFlowWrapper } from "./BrainRiverFlowWrapper";

export const dynamic = "force-dynamic";

export default async function MemoryPage() {
  const [mem, health, decisions] = await Promise.all([
    getMemorySummary(),
    getHealth(),
    getDecisions(50),
  ]);

  if (!mem) {
    return (
      <div className="space-y-6">
        <h1 className="text-3xl font-bold tracking-tight text-tron-text">
          Brain & Memory
        </h1>
        <div className="tron-panel p-8 text-center text-tron-dim">
          Memory nicht verfügbar. Stelle sicher, dass der Operator Brain läuft.
        </div>
      </div>
    );
  }

  const { totals } = mem;

  // Build latest cycle from recent decisions: collect most recent entry per phase
  const latestTrace = (() => {
    const seen = new Set<string>();
    const result: typeof decisions = [];
    for (const d of decisions) {
      const phase = d.phase?.toLowerCase();
      if (phase && !seen.has(phase)) {
        seen.add(phase);
        result.push(d);
      }
    }
    return result;
  })();

  return (
    <div className="space-y-6 animate-fade-in">
      {/* River Flow Hero */}
      <div
        className="rounded-xl p-6"
        style={{
          background: "linear-gradient(180deg, var(--tron-bg-panel), var(--tron-bg))",
          border: "1px solid var(--tron-border)",
        }}
      >
        <BrainRiverFlowWrapper
          latestTrace={latestTrace}
          totalCycles={totals?.decisions ?? 0}
          totalReflections={totals?.reflections ?? 0}
          avgQuality={totals?.avg_quality ?? 0}
          brain={health?.brain ?? null}
        />
      </div>

      {/* Stats Grid */}
      <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-6 gap-3">
        {[
          { label: "Ereignisse", value: totals?.episodes ?? 0, color: "var(--tron-text)" },
          { label: "Entscheidungen", value: totals?.decisions ?? 0, color: "var(--tron-accent)" },
          { label: "Reflections", value: totals?.reflections ?? 0, color: "#ec4899" },
          { label: "Ø Qualität", value: totals?.avg_quality != null ? totals.avg_quality.toFixed(2) : "—", color: "var(--tron-success)" },
          { label: "Prinzipien", value: totals?.principles ?? "—", color: "#8b5cf6" },
          { label: "Outcomes", value: totals?.outcomes ?? "—", color: "#f59e0b" },
        ].map((s) => (
          <div key={s.label} className="stat-card">
            <div className="text-[10px] uppercase font-mono tracking-wider" style={{ color: "var(--tron-text-dim)" }}>
              {s.label}
            </div>
            <div className="text-2xl font-bold font-mono mt-1" style={{ color: s.color }}>
              {s.value}
            </div>
          </div>
        ))}
      </div>

      {/* Tabs */}
      <BrainTabs memorySummary={mem} />
    </div>
  );
}
