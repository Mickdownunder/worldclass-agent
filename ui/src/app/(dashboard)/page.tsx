import Link from "next/link";
import { getHealth } from "@/lib/operator/health";
import { listResearchProjects } from "@/lib/operator/research";
import { DashboardQuickActions } from "@/components/DashboardQuickActions";
import { EventFeed } from "@/components/EventFeed";
import { StatusBadge } from "@/components/StatusBadge";

export const dynamic = "force-dynamic";

const PHASE_ORDER = ["explore", "focus", "connect", "verify", "synthesize"];
function phaseProgress(phase: string): number {
  const i = PHASE_ORDER.indexOf(phase.toLowerCase());
  if (i < 0) return 0;
  return ((i + 1) / PHASE_ORDER.length) * 100;
}

export default async function CommandCenterPage() {
  const [health, projects] = await Promise.all([
    getHealth(),
    listResearchProjects(),
  ]);
  const healthy = health.healthy ?? false;
  const failures = health.recent_failures ?? [];
  const activeProjects = projects.filter(
    (p) => p.status !== "done" && p.status !== "failed"
  );

  return (
    <div className="space-y-8">
      <div className="flex flex-wrap items-center justify-between gap-4">
        <div>
          <h1 className="text-3xl font-bold tracking-tight text-tron-text">
            Command Center
          </h1>
          <p className="mt-1 text-sm text-tron-muted">
            Deine Steuerzentrale – hier siehst du auf einen Blick, ob alles läuft und was zu tun ist.
          </p>
        </div>
        <Link
          href="/research"
          className="flex h-10 items-center justify-center rounded-sm bg-transparent border-2 border-tron-accent px-5 text-sm font-bold text-tron-accent shadow-[0_0_15px_var(--tron-glow)] transition-all hover:bg-tron-accent hover:text-black hover:shadow-[0_0_25px_var(--tron-glow)] active:scale-[0.98] uppercase tracking-wider"
        >
          Neues Research-Projekt
        </Link>
      </div>

      {/* System-Health: für Menschen lesbar */}
      <section className="tron-panel px-4 py-4">
        <div className="flex flex-wrap items-center gap-4 text-sm">
          <span
            className={`font-medium ${healthy ? "text-tron-success" : "text-tron-error"}`}
          >
            {healthy ? "Alles in Ordnung" : "Achtung: etwas ist schiefgelaufen"}
          </span>
          {health.disk_used_pct != null && (
            <span className="text-tron-dim">
              Speicher: <span className="text-tron-text">{health.disk_used_pct}%</span> belegt
            </span>
          )}
          {health.load_1m != null && (
            <span className="text-tron-dim">
              Auslastung: <span className="text-tron-text">{health.load_1m}</span>
            </span>
          )}
          {health.jobs_failed != null && health.jobs_failed > 0 && (
            <span className="text-tron-error">
              {health.jobs_failed} {health.jobs_failed === 1 ? "Lauf" : "Läufe"} fehlgeschlagen
            </span>
          )}
        </div>
        {failures.length > 0 && (
          <div className="mt-3 rounded border border-tron-error/30 bg-tron-error/5 px-3 py-2">
            <p className="text-sm font-medium text-tron-text">
              Was tun? Fehlgeschlagene Läufe ansehen und ggf. erneut versuchen (Retry):
            </p>
            <ul className="mt-1.5 list-inside list-disc text-xs text-tron-muted">
              {failures.slice(0, 3).map((f, i) => (
                <li key={i}>{f}</li>
              ))}
            </ul>
            <Link
              href="/jobs?status=FAILED"
              className="mt-2 inline-block text-sm font-medium text-tron-accent hover:underline"
            >
              → Fehlgeschlagene Jobs ansehen
            </Link>
          </div>
        )}
      </section>

      {/* Mitte: Research-Projekte | Letzte Aktionen */}
      <div className="grid gap-6 lg:grid-cols-2">
        <section className="tron-panel p-4">
          <h2 className="mb-3 text-lg font-medium text-tron-muted">
            Aktive Research-Projekte
          </h2>
          {activeProjects.length === 0 ? (
            <p className="text-sm text-tron-dim">
              Keine aktiven Projekte.{" "}
              <Link href="/research" className="text-tron-accent hover:underline">
                Neues Projekt starten
              </Link>
            </p>
          ) : (
            <ul className="space-y-3">
              {activeProjects.slice(0, 5).map((p) => (
                <li key={p.id}>
                  <Link
                    href={`/research/${p.id}`}
                    className="tron-panel block border-tron-border p-3 transition hover:border-tron-accent/40"
                  >
                    <div className="flex items-center justify-between gap-2">
                      <span className="truncate font-medium text-tron-text">
                        {p.question || p.id}
                      </span>
                      <StatusBadge status={p.status} />
                    </div>
                    <div className="mt-1.5 flex items-center gap-2 text-xs text-tron-dim">
                      <span>{p.phase}</span>
                      <span>·</span>
                      <span>{p.findings_count} Findings</span>
                    </div>
                    <div className="mt-1.5 h-1 w-full overflow-hidden rounded-full bg-tron-bg">
                      <div
                        className="h-full rounded-full bg-tron-accent transition-all"
                        style={{ width: `${phaseProgress(p.phase)}%` }}
                      />
                    </div>
                  </Link>
                </li>
              ))}
            </ul>
          )}
        </section>

        <section className="tron-panel p-4">
          <h2 className="mb-3 text-lg font-medium text-tron-muted">
            Was zuletzt passiert ist
          </h2>
          <EventFeed />
        </section>
      </div>

      {/* Quick-Actions: wofür sie da sind */}
      <section className="tron-panel p-4">
        <h2 className="mb-3 text-lg font-medium text-tron-muted">
          Schnellstart
        </h2>
        <p className="mb-4 text-sm text-tron-dim">
          <strong className="text-tron-text">Factory:</strong> Einmal Discover → Pack → Deliver durchlaufen lassen. –
          <strong className="text-tron-text ml-1"> Brain:</strong> Das System wählt den nächsten Schritt selbst (z. B. Research vorantreiben, Infra prüfen) und führt ihn aus.
        </p>
        <DashboardQuickActions />
      </section>

      <div className="flex flex-wrap gap-4">
        <Link
          href="/jobs"
          className="flex h-10 items-center justify-center rounded-sm border-2 border-tron-border bg-transparent px-5 text-sm font-bold text-tron-text shadow-[0_0_10px_var(--tron-glow)] transition-all hover:border-tron-accent hover:text-tron-accent hover:shadow-[0_0_20px_var(--tron-glow)] active:scale-[0.98] uppercase tracking-wider"
        >
          Jobs anzeigen
        </Link>
        <Link
          href="/packs"
          className="flex h-10 items-center justify-center rounded-sm border-2 border-tron-border bg-transparent px-5 text-sm font-bold text-tron-text shadow-[0_0_10px_var(--tron-glow)] transition-all hover:border-tron-accent hover:text-tron-accent hover:shadow-[0_0_20px_var(--tron-glow)] active:scale-[0.98] uppercase tracking-wider"
        >
          Packs anzeigen
        </Link>
        <Link
          href="/memory"
          className="flex h-10 items-center justify-center rounded-sm border-2 border-tron-border bg-transparent px-5 text-sm font-bold text-tron-text shadow-[0_0_10px_var(--tron-glow)] transition-all hover:border-tron-accent hover:text-tron-accent hover:shadow-[0_0_20px_var(--tron-glow)] active:scale-[0.98] uppercase tracking-wider"
        >
          Brain & Memory
        </Link>
      </div>
    </div>
  );
}
