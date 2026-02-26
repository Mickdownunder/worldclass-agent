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

      <section className="tron-panel p-6">
        <h2 className="mb-4 text-lg font-medium text-tron-muted">Strategic Principles</h2>
        <p className="mb-3 text-[12px] text-tron-dim">Guiding and cautionary principles from past research (EvolveR).</p>
        <ul className="space-y-3">
          {(principles ?? []).map((p, i) => (
            <li key={p.id ?? i} className="flex flex-wrap items-start gap-2 text-sm border-l-2 pl-3" style={{ borderColor: (p.principle_type === "cautionary" ? "var(--tron-error)" : "var(--tron-success)") }}>
              <span className="rounded px-1.5 py-0.5 font-mono text-[10px] font-bold uppercase" style={{ background: "var(--tron-bg)", color: "var(--tron-text-muted)" }}>
                {p.principle_type ?? "guiding"}
              </span>
              <span className="text-tron-text">{(p.description ?? "").slice(0, 300)}{(p.description?.length ?? 0) > 300 ? "…" : ""}</span>
              <span className="text-tron-dim text-[11px]">score: {(p.metric_score ?? 0).toFixed(2)} · use: {p.usage_count ?? 0}</span>
              {p.domain && <span className="text-tron-accent text-[11px]">{p.domain}</span>}
            </li>
          ))}
        </ul>
        {(principles?.length ?? 0) === 0 && <p className="text-tron-dim">Noch keine Prinzipien.</p>}
      </section>

      <section className="tron-panel p-6">
        <h2 className="mb-4 text-lg font-medium text-tron-muted">Source Credibility</h2>
        <p className="mb-3 text-[12px] text-tron-dim">Domain-level learned credibility from verification outcomes.</p>
        <div className="overflow-x-auto">
          <table className="w-full text-[12px]">
            <thead>
              <tr className="text-left text-tron-dim border-b border-tron-border">
                <th className="pb-2 pr-4">Domain</th>
                <th className="pb-2 pr-4">Used</th>
                <th className="pb-2 pr-4">Verified</th>
                <th className="pb-2 pr-4">Failed</th>
                <th className="pb-2">Credibility</th>
              </tr>
            </thead>
            <tbody>
              {(credibility ?? []).map((c, i) => {
                const cred = c.learned_credibility ?? 0;
                const credColor = cred >= 0.7 ? "var(--tron-success)" : cred >= 0.4 ? "var(--tron-amber, #f59e0b)" : "var(--tron-error)";
                return (
                  <tr key={c.domain ?? i} className="border-b border-tron-border/50">
                    <td className="py-2 pr-4 font-mono text-tron-text">{c.domain}</td>
                    <td className="py-2 pr-4 text-tron-muted">{c.times_used ?? 0}</td>
                    <td className="py-2 pr-4 text-tron-muted">{c.verified_count ?? 0}</td>
                    <td className="py-2 pr-4 text-tron-muted">{c.failed_verification_count ?? 0}</td>
                    <td className="py-2 font-semibold" style={{ color: credColor }}>{(cred * 100).toFixed(0)}%</td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
        {(credibility?.length ?? 0) === 0 && <p className="text-tron-dim mt-2">Noch keine Credibility-Daten.</p>}
      </section>

      <section className="tron-panel p-6">
        <h2 className="mb-4 text-lg font-medium text-tron-muted">Project Outcomes</h2>
        <p className="mb-3 text-[12px] text-tron-dim">Research project outcomes (total: {outcomesTotal ?? 0}).</p>
        <ul className="space-y-2">
          {(outcomes ?? []).slice(0, 20).map((o, i) => (
            <li key={i} className="flex flex-wrap items-center gap-2 text-sm">
              <Link href={`/research/${o.project_id ?? ""}`} className="font-mono text-tron-accent hover:underline">
                {o.project_id ?? "—"}
              </Link>
              <span className="text-tron-dim">{o.domain ?? ""}</span>
              <span className="text-tron-muted">critic: {(o.critic_score ?? 0).toFixed(2)}</span>
              <span className="rounded px-1 py-0.5 text-[10px]" style={{ background: "var(--tron-bg)", color: "var(--tron-text-muted)" }}>{o.user_verdict ?? "—"}</span>
              <span className="text-tron-dim text-[11px]">{o.completed_at ?? ""}</span>
            </li>
          ))}
        </ul>
        {(outcomes?.length ?? 0) === 0 && <p className="text-tron-dim">Noch keine Outcomes.</p>}
      </section>

      <section className="tron-panel p-6">
        <h2 className="mb-4 text-lg font-medium text-tron-muted">Brain Cognitive Traces (Decisions)</h2>
        <p className="mb-3 text-[12px] text-tron-dim">Recent perceive → think → decide steps.</p>
        <ul className="space-y-3">
          {(decisions ?? []).map((d, i) => (
            <li key={d.id ?? i} className="text-sm border-l-2 border-tron-accent/40 pl-3">
              <span className="text-tron-accent font-mono text-[11px]">{d.phase}</span>
              <span className="mx-2 text-tron-dim">·</span>
              <span className="text-tron-dim text-[11px]">{d.ts}</span>
              {d.reasoning != null && <p className="mt-1 text-tron-text">{(d.reasoning as string).slice(0, 200)}…</p>}
              <span className="text-tron-muted text-[11px]">confidence: {(d.confidence ?? 0).toFixed(2)}</span>
            </li>
          ))}
        </ul>
        {(decisions?.length ?? 0) === 0 && <p className="text-tron-dim">Noch keine Decisions.</p>}
      </section>

      <section className="tron-panel p-6">
        <h2 className="mb-4 text-lg font-medium text-tron-muted">Entities</h2>
        <p className="mb-3 text-[12px] text-tron-dim">Knowledge graph entities (name, type, first seen).</p>
        <div className="overflow-x-auto">
          <table className="w-full text-[12px]">
            <thead>
              <tr className="text-left text-tron-dim border-b border-tron-border">
                <th className="pb-2 pr-4">Name</th>
                <th className="pb-2 pr-4">Type</th>
                <th className="pb-2">First seen project</th>
              </tr>
            </thead>
            <tbody>
              {(entities ?? []).slice(0, 50).map((e, i) => (
                <tr key={e.id ?? i} className="border-b border-tron-border/50">
                  <td className="py-2 pr-4 font-mono text-tron-text">{e.name ?? "—"}</td>
                  <td className="py-2 pr-4 text-tron-muted">{e.type ?? "—"}</td>
                  <td className="py-2 text-tron-dim">{e.first_seen_project ?? "—"}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        {(entities?.length ?? 0) === 0 && <p className="text-tron-dim mt-2">Noch keine Entities.</p>}
      </section>
    </div>
  );
}
