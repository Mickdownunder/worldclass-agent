import Link from "next/link";
import { notFound } from "next/navigation";
import { getResearchProject, getLatestReportMarkdown } from "@/lib/operator/research";
import { StatusBadge } from "@/components/StatusBadge";
import { StartCycleButton } from "@/components/StartCycleButton";
import { CreateFollowupButton } from "@/components/CreateFollowupButton";
import { ResearchDetailTabs } from "./ResearchDetailTabs";

export const dynamic = "force-dynamic";

const PHASE_ORDER = ["explore", "focus", "connect", "verify", "synthesize"];
function phaseProgress(phase: string): number {
  const i = PHASE_ORDER.indexOf(phase.toLowerCase());
  if (i < 0) return 0;
  return ((i + 1) / PHASE_ORDER.length) * 100;
}

export default async function ResearchProjectPage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const id = (await params).id;
  const project = await getResearchProject(id);
  if (!project) notFound();

  const markdown = await getLatestReportMarkdown(id);
  const progress = phaseProgress(project.phase);

  return (
    <div className="space-y-6">
      <div className="flex items-center gap-4">
        <Link href="/research" className="text-sm text-tron-muted hover:text-tron-accent transition-colors">
          ← Zurück zur Übersicht
        </Link>
      </div>

      {/* Hero-Bereich */}
      <div className="space-y-6">
        <h1 className="text-2xl sm:text-3xl font-semibold tracking-tight text-tron-text leading-snug">
          {project.question || "Ohne Forschungsfrage"}
        </h1>
        
        <div className="flex flex-col gap-2">
          <div className="flex items-baseline gap-3">
            <span className="text-sm font-medium text-tron-dim uppercase tracking-widest">Aktuelle Phase:</span>
            <span 
              className="text-4xl sm:text-5xl font-bold uppercase text-tron-accent" 
              style={{ textShadow: "0 0 20px var(--tron-glow), 0 0 40px var(--tron-glow)" }}
            >
              {project.phase}
            </span>
          </div>
          <div className="mt-2 h-1.5 w-full overflow-hidden rounded-full bg-tron-bg border border-tron-border/30">
            <div
              className="h-full rounded-full bg-tron-accent transition-all duration-500 ease-out"
              style={{ width: `${progress}%`, boxShadow: "0 0 10px var(--tron-glow)" }}
            />
          </div>
        </div>
      </div>

      {/* Metadaten-Block (kompakt) */}
      <div className="flex flex-wrap items-center gap-x-6 gap-y-3 text-sm text-tron-dim">
        <div className="flex items-center gap-2">
          <span className="uppercase tracking-widest text-xs">Projekt:</span>
          <span className="font-mono">{project.id}</span>
        </div>
        <StatusBadge status={project.status} />
        <div className="flex gap-4 border-l border-tron-border/50 pl-6">
          <span>{project.findings_count} <span className="text-tron-muted">Findings</span></span>
          <span>{project.reports_count} <span className="text-tron-muted">Reports</span></span>
          {project.feedback_count > 0 && (
            <span>{project.feedback_count} <span className="text-tron-muted">Feedbacks</span></span>
          )}
        </div>
      </div>

      {/* Aktionen */}
      <div className="flex flex-wrap gap-4 pt-2">
        {project.status !== "done" && (
          <StartCycleButton projectId={id} />
        )}
        {project.status === "done" && (
          <CreateFollowupButton projectId={id} />
        )}
      </div>

      <section className="tron-panel p-6 mt-8">
        <h2 className="mb-6 text-xl font-medium text-tron-text">Zusammenfassung & Details</h2>
        <ResearchDetailTabs projectId={id} initialMarkdown={markdown} />
      </section>
    </div>
  );
}
