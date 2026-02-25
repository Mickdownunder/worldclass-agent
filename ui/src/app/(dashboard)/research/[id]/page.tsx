import Link from "next/link";
import { notFound } from "next/navigation";
import { getResearchProject, getLatestReportMarkdown } from "@/lib/operator/research";
import { ReportView } from "./ReportView";

export const dynamic = "force-dynamic";

export default async function ResearchProjectPage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const id = (await params).id;
  const project = await getResearchProject(id);
  if (!project) notFound();

  const markdown = await getLatestReportMarkdown(id);

  return (
    <div className="space-y-6">
      <div className="flex items-center gap-4">
        <Link href="/research" className="text-sm text-[#88aacc] hover:text-[#00d4ff]">
          ← Research
        </Link>
      </div>

      <h1 className="text-2xl font-semibold tracking-wide text-[#00d4ff]">
        {project.id}
      </h1>

      <div className="tron-panel p-4">
        <p className="text-[#c0e0ff]">{project.question}</p>
        <div className="mt-2 flex flex-wrap gap-4 text-sm text-[#88aacc]">
          <span>Status: {project.status}</span>
          <span>Phase: {project.phase}</span>
          <span>Findings: {project.findings_count}</span>
          <span>Reports: {project.reports_count}</span>
          {project.feedback_count > 0 && (
            <span>Feedback: {project.feedback_count}</span>
          )}
        </div>
      </div>

      <section className="tron-panel p-6">
        <h2 className="mb-4 text-lg font-medium text-[#88aacc]">Report</h2>
        {markdown ? (
          <ReportView markdown={markdown} projectId={id} />
        ) : (
          <p className="text-[#6688aa]">Noch kein Report. Führe research-cycle oder research-synthesize aus.</p>
        )}
      </section>
    </div>
  );
}
