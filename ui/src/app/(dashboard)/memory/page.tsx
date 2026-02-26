import Link from "next/link";
import {
  getMemorySummary,
  getPrinciples,
  getSourceCredibility,
  getProjectOutcomes,
  getDecisions,
  getEntities,
} from "@/lib/operator/memory";

export const dynamic = "force-dynamic";

export default async function MemoryPage() {
  const [mem, principles, credibility, { outcomes, total: outcomesTotal }, decisions, { entities }] = await Promise.all([
    getMemorySummary(),
    getPrinciples(50),
    getSourceCredibility(50),
    getProjectOutcomes(100),
    getDecisions(30),
    getEntities(),
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
  const { totals, recent_episodes, recent_reflections, playbooks } = mem;
  return (
    <div className="space-y-6">
      <h1 className="text-3xl font-bold tracking-tight text-tron-text">
        Brain & Gedächtnis
      </h1>
      <p className="max-w-xl text-sm text-tron-muted">
        Hier siehst du, was das System aus vergangenen Aufgaben gelernt hat (Reflections) und welche Strategien es für die Zukunft anwendet (Playbooks).
      </p>
      <section className="tron-panel p-6 mt-4">
        <h2 className="mb-4 text-lg font-medium text-tron-muted">Zusammenfassung</h2>
        <div className="flex flex-wrap gap-6">
          <div>
            <span className="text-tron-dim">Ereignisse</span>
            <span className="ml-2 text-tron-text">{totals.episodes ?? 0}</span>
          </div>
          <div>
            <span className="text-tron-dim">Entscheidungen</span>
            <span className="ml-2 text-tron-text">{totals.decisions ?? 0}</span>
          </div>
          <div>
            <span className="text-tron-dim">Lern-Notizen</span>
            <span className="ml-2 text-tron-text">{totals.reflections ?? 0}</span>
          </div>
          <div>
            <span className="text-tron-dim">Ø Qualität</span>
            <span className="ml-2 text-tron-success">
              {totals.avg_quality != null ? totals.avg_quality.toFixed(2) : "—"}
            </span>
          </div>
        </div>
      </section>
      <section className="tron-panel p-6">
        <h2 className="mb-4 text-lg font-medium text-tron-muted">Letzte Ereignisse</h2>
        <ul className="space-y-2">
          {(recent_episodes ?? []).slice(0, 15).map((e, i) => (
            <li key={i} className="flex gap-3 text-sm">
              <span className="text-tron-dim shrink-0">{e.ts}</span>
              <span className="text-tron-accent">{e.kind}</span>
              <span className="text-tron-text">{e.content}</span>
            </li>
          ))}
        </ul>
        {(recent_episodes?.length ?? 0) === 0 && (
          <p className="text-tron-dim">Noch keine Episoden.</p>
        )}
      </section>
      <section className="tron-panel p-6">
        <h2 className="mb-4 text-lg font-medium text-tron-muted">Was das System gelernt hat (Reflections)</h2>
        <ul className="space-y-3">
          {(recent_reflections ?? []).slice(0, 10).map((r, i) => (
            <li key={i} className="border-l-2 border-tron-accent/30 pl-3 text-sm">
              <span className="text-tron-dim">{r.ts}</span>
              <span className="ml-2 text-tron-success">Q: {r.quality}</span>
              {r.learnings != null && (
                <p className="mt-1 text-tron-text">{r.learnings}</p>
              )}
            </li>
          ))}
        </ul>
        {(recent_reflections?.length ?? 0) === 0 && (
          <p className="text-tron-dim">Noch keine Reflexionen.</p>
        )}
      </section>
      <section className="tron-panel p-6">
        <h2 className="mb-4 text-lg font-medium text-tron-muted">Angewandte Strategien (Playbooks)</h2>
        <ul className="space-y-2">
          {(playbooks ?? []).map((p, i) => (
            <li key={i} className="text-sm">
              <span className="text-tron-accent">{p.domain}</span>
              <span className="mx-2 text-tron-dim">·</span>
              <span className="text-tron-text">{p.strategy}</span>
              <span className="ml-2 text-tron-muted">({(p.success_rate * 100).toFixed(0)}%)</span>
            </li>
          ))}
        </ul>
        {(playbooks?.length ?? 0) === 0 && (
          <p className="text-tron-dim">Noch keine Playbooks.</p>
        )}
      </section>
    </div>
  );
}
