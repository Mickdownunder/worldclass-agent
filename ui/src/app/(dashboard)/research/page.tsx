import Link from "next/link";
import { listResearchProjects } from "@/lib/operator/research";
import { StatusBadge } from "@/components/StatusBadge";
import { EmptyState } from "@/components/EmptyState";
import { CreateProjectForm } from "@/components/CreateProjectForm";

export const dynamic = "force-dynamic";

export default async function ResearchPage() {
  const projects = await listResearchProjects();

  return (
    <div className="space-y-6">
      <h1 className="text-3xl font-bold tracking-tight text-tron-text">
        Forschungsprojekte
      </h1>

      <p className="max-w-xl text-sm text-tron-muted">
        Deine Forschungsprojekte. Klicke auf ein Projekt, um Fortschritt und Report zu sehen.
      </p>

      <CreateProjectForm />

      {projects.length === 0 ? (
        <EmptyState
          title="Noch keine Projekte."
          description="Erstelle oben ein neues Forschungsprojekt."
        />
      ) : (
        <div className="grid gap-4 mt-6">
          {projects.map((p) => (
            <Link
              key={p.id}
              href={`/research/${p.id}`}
              className="tron-panel block border-tron-border p-5 transition-all hover:border-tron-accent hover:shadow-[0_0_20px_var(--tron-glow-accent)]"
            >
              <div className="flex flex-col sm:flex-row sm:items-start justify-between gap-4">
                <div className="space-y-1.5">
                  <h3 className="text-lg font-semibold text-tron-text leading-snug">
                    {p.question || "Ohne Forschungsfrage"}
                  </h3>
                  <div className="text-xs text-tron-dim font-mono">Projekt-ID: {p.id}</div>
                </div>
                <div className="flex shrink-0 flex-col items-end gap-2">
                  <StatusBadge status={p.status} className="shadow-sm" />
                  <span className="text-sm font-bold uppercase text-tron-accent tracking-widest text-shadow-[0_0_8px_var(--tron-glow)]">
                    Phase: {p.phase}
                  </span>
                </div>
              </div>
              
              <div className="mt-4 flex flex-wrap gap-4 text-sm text-tron-muted border-t border-tron-border/30 pt-3">
                <div className="flex items-center gap-1.5">
                  <span className="text-tron-text font-medium">{p.findings_count}</span>
                  <span>Findings</span>
                </div>
                <div className="flex items-center gap-1.5">
                  <span className="text-tron-text font-medium">{p.reports_count}</span>
                  <span>Reports</span>
                </div>
              </div>
            </Link>
          ))}
        </div>
      )}
    </div>
  );
}
