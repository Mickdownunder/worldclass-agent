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

      {/* Vitals Grid (Top Row) */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
        {/* Memory Value Card */}
        <div className="tron-panel p-5 relative overflow-hidden flex flex-col justify-between">
          <div>
            <div className="text-[10px] font-semibold uppercase tracking-wider text-tron-muted flex justify-between">
              <span>Memory Value</span>
              <span className="text-[9px] opacity-70">applied Ø vs fallback Ø</span>
            </div>
            <div className="mt-2 text-4xl font-mono font-bold" style={{ color: "var(--tron-accent)" }}>
              {totals?.memory_value?.memory_value != null
                ? totals.memory_value.memory_value > 0
                  ? `+${totals.memory_value.memory_value.toFixed(2)}`
                  : totals.memory_value.memory_value.toFixed(2)
                : "—"}
            </div>
          </div>
          <div className="mt-4 pt-3 border-t border-tron-border/30 flex justify-between text-xs text-tron-dim font-mono">
            <span>app: {totals?.memory_value?.applied_avg ?? "—"}</span>
            <span>fb: {totals?.memory_value?.fallback_avg ?? "—"}</span>
          </div>
        </div>

        {/* Run Episodes Card */}
        <div className="tron-panel p-5 flex flex-col justify-between">
          <div>
            <div className="text-[10px] font-semibold uppercase tracking-wider text-tron-muted">
              Run Episodes
            </div>
            <div className="mt-2 text-4xl font-mono font-bold text-[#c678ff]">
              {totals?.run_episodes ?? 0}
            </div>
          </div>
          <div className="mt-4 pt-3 border-t border-tron-border/30 text-xs text-tron-dim flex justify-between">
            <span>Total executions</span>
            <span className="text-tron-text">{totals?.episodes ?? 0} evts</span>
          </div>
        </div>

        {/* Quality Card */}
        <div className="tron-panel p-5 flex flex-col justify-between">
          <div>
            <div className="text-[10px] font-semibold uppercase tracking-wider text-tron-muted">
              Quality
            </div>
            <div className="mt-2 text-4xl font-mono font-bold text-tron-text">
              {totals?.avg_quality != null ? `${(totals.avg_quality * 100).toFixed(0)}%` : "—"}
            </div>
          </div>
          <div className="mt-4 pt-3 border-t border-tron-border/30 text-xs text-tron-dim flex justify-between">
            <span>Avg critic score</span>
            <span>{totals?.reflections ?? 0} reflections</span>
          </div>
        </div>

        {/* Principles / Outcomes Card */}
        <div className="tron-panel p-5 flex flex-col justify-between">
          <div>
            <div className="text-[10px] font-semibold uppercase tracking-wider text-tron-muted flex justify-between">
              <span>Principles</span>
              <span className="text-[9px] opacity-70">Outcomes</span>
            </div>
            <div className="mt-2 flex items-baseline justify-between">
              <span className="text-4xl font-mono font-bold text-tron-success">
                {totals?.principles ?? 0}
              </span>
              <span className="text-2xl font-mono font-bold opacity-50" style={{ color: "#f59e0b" }}>
                {totals?.outcomes ?? 0}
              </span>
            </div>
          </div>
          <div className="mt-4 pt-3 border-t border-tron-border/30 text-xs text-tron-dim">
            Synthesized knowledge
          </div>
        </div>
      </div>

      {/* Tabs */}
      <BrainTabs memorySummary={mem} />
    </div>
  );
}
