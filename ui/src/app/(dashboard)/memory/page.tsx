import { getMemorySummary } from "@/lib/operator/memory";
import { BrainTabs } from "./BrainTabs";

export const dynamic = "force-dynamic";

export default async function MemoryPage() {
  const mem = await getMemorySummary();

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
