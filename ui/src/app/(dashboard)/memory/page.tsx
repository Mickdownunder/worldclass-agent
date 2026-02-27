import { getMemorySummary } from "@/lib/operator/memory";
import { getHealth } from "@/lib/operator/health";
import { BrainTabs } from "./BrainTabs";

export const dynamic = "force-dynamic";

export default async function MemoryPage() {
  const [mem, health] = await Promise.all([getMemorySummary(), getHealth()]);

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

  return (
    <div className="space-y-6">
      <h1 className="text-3xl font-bold tracking-tight text-tron-text">
        Brain & Gedächtnis
      </h1>
      <p className="max-w-xl text-sm text-tron-muted">
        Hier siehst du, was das System aus vergangenen Aufgaben gelernt hat (Reflections) und welche Strategien es für die Zukunft anwendet (Playbooks).
      </p>

      {/* Brain process status: läuft oder hängt */}
      {health?.brain && ((health.brain.cycle?.count ?? 0) + (health.brain.reflect?.count ?? 0) > 0) && (
        <div
          className="rounded-lg px-4 py-3 flex flex-wrap items-center gap-3"
          style={{
            background: health.brain.cycle?.stuck || health.brain.reflect?.stuck
              ? "rgba(245,158,11,0.08)"
              : "var(--tron-bg-panel)",
            border: `1px solid ${health.brain.cycle?.stuck || health.brain.reflect?.stuck ? "rgba(245,158,11,0.4)" : "var(--tron-border)"}`,
          }}
        >
          <span className="text-[11px] font-semibold uppercase font-mono" style={{ color: "var(--tron-text-muted)" }}>
            Brain-Prozesse
          </span>
          <span className="font-mono text-sm" style={{ color: "var(--tron-text)" }}>
            {health.brain.cycle?.count ? `${health.brain.cycle.count} Cycle` : ""}
            {health.brain.cycle?.count && health.brain.reflect?.count ? " · " : ""}
            {health.brain.reflect?.count ? `${health.brain.reflect.count} Reflect` : ""}
          </span>
          {health.brain.cycle?.max_elapsed_sec != null && health.brain.cycle.max_elapsed_sec > 0 && (
            <span className="text-[11px]" style={{ color: "var(--tron-text-dim)" }}>
              längster Cycle: {Math.round(health.brain.cycle.max_elapsed_sec / 60)} min
            </span>
          )}
          {health.brain.reflect?.max_elapsed_sec != null && health.brain.reflect.max_elapsed_sec > 0 && (
            <span className="text-[11px]" style={{ color: "var(--tron-text-dim)" }}>
              längster Reflect: {Math.round(health.brain.reflect.max_elapsed_sec / 60)} min
            </span>
          )}
          {(health.brain.cycle?.stuck || health.brain.reflect?.stuck) && (
            <span
              className="text-[11px] font-semibold"
              style={{ color: "var(--tron-warning, #f59e0b)" }}
            >
              {"⚠ Hängend (Cycle >10 min oder Reflect >5 min) — ggf. Prozesse beenden: pkill -f 'bin/brain'"}
            </span>
          )}
        </div>
      )}

      {/* Top: Stats Bar */}
      <div className="grid grid-cols-2 md:grid-cols-4 lg:grid-cols-6 gap-4 mt-4">
        <div className="stat-card">
          <div className="text-[10px] text-tron-dim uppercase font-mono tracking-wider">Ereignisse</div>
          <div className="text-2xl text-tron-text mt-1">{totals?.episodes ?? 0}</div>
        </div>
        <div className="stat-card">
          <div className="text-[10px] text-tron-dim uppercase font-mono tracking-wider">Entscheidungen</div>
          <div className="text-2xl text-tron-text mt-1">{totals?.decisions ?? 0}</div>
        </div>
        <div className="stat-card">
          <div className="text-[10px] text-tron-dim uppercase font-mono tracking-wider">Lern-Notizen</div>
          <div className="text-2xl text-tron-text mt-1">{totals?.reflections ?? 0}</div>
        </div>
        <div className="stat-card">
          <div className="text-[10px] text-tron-dim uppercase font-mono tracking-wider">Ø Qualität</div>
          <div className="text-2xl text-tron-success mt-1">
            {totals?.avg_quality != null ? totals.avg_quality.toFixed(2) : "—"}
          </div>
        </div>
        <div className="stat-card">
          <div className="text-[10px] text-tron-dim uppercase font-mono tracking-wider">Prinzipien</div>
          <div className="text-2xl text-tron-text mt-1">{totals?.principles ?? "—"}</div>
        </div>
        <div className="stat-card">
          <div className="text-[10px] text-tron-dim uppercase font-mono tracking-wider">Outcomes</div>
          <div className="text-2xl text-tron-text mt-1">{totals?.outcomes ?? "—"}</div>
        </div>
      </div>

      <BrainTabs memorySummary={mem} />
    </div>
  );
}
