import Link from "next/link";
import { listResearchProjects } from "@/lib/operator/research";

export const dynamic = "force-dynamic";

export default async function ResearchPage() {
  const projects = await listResearchProjects();

  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-semibold tracking-wide text-[#00d4ff]">
        Research
      </h1>

      <p className="max-w-xl text-sm text-[#88aacc]">
        Autonome Forschungsprojekte. Jedes Projekt durchläuft Phasen: Explore → Focus → Connect → Verify → Synthesize. Reports erscheinen unter „Reports“ pro Projekt.
      </p>

      {projects.length === 0 ? (
        <div className="tron-panel p-6 text-[#6688aa]">
          Noch keine Research-Projekte. Erstelle eines per Job: <code className="text-[#00d4ff]">op job new --workflow research-init --request &quot;Deine Frage&quot;</code>
        </div>
      ) : (
        <div className="tron-panel overflow-hidden">
          <table className="w-full text-left text-sm">
            <thead>
              <tr className="border-b border-[#00d4ff]/20 text-[#88aacc]">
                <th className="p-3">Projekt</th>
                <th className="p-3">Frage</th>
                <th className="p-3">Status / Phase</th>
                <th className="p-3">Findings</th>
                <th className="p-3">Reports</th>
                <th className="p-3"></th>
              </tr>
            </thead>
            <tbody>
              {projects.map((p) => (
                <tr key={p.id} className="border-b border-[#00d4ff]/10">
                  <td className="p-3 font-mono text-[#00d4ff]">{p.id}</td>
                  <td className="max-w-md truncate p-3 text-[#c0e0ff]" title={p.question}>
                    {p.question}
                  </td>
                  <td className="p-3">
                    <span className="text-[#88aacc]">{p.status}</span>
                    <span className="ml-1 text-[#6688aa]">/ {p.phase}</span>
                  </td>
                  <td className="p-3 text-[#c0e0ff]">{p.findings_count}</td>
                  <td className="p-3 text-[#c0e0ff]">{p.reports_count}</td>
                  <td className="p-3">
                    <Link
                      href={`/research/${p.id}`}
                      className="text-[#00d4ff] hover:underline"
                    >
                      Öffnen
                    </Link>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
