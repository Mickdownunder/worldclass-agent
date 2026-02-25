import { listAgents, listWorkflows } from "@/lib/operator/agents";

export const dynamic = "force-dynamic";

export default async function AgentsPage() {
  const [agents, workflows] = await Promise.all([listAgents(), listWorkflows()]);

  return (
    <div className="space-y-8">
      <h1 className="text-3xl font-bold tracking-tight text-tron-text">
        Agents & Workflows
      </h1>

      <p className="max-w-xl text-sm text-tron-muted">
        <strong className="text-tron-text">June</strong> ist der OpenClaw-Agent, mit dem du in Telegram schreibst. <strong className="text-tron-text">Captain</strong> ist das Agent-System (Operator): Brain, Workflows, Jobs – nicht OpenClaw. Darunter die Workflows, die Captain nutzt.
      </p>

      <section>
        <h2 className="mb-4 text-lg font-medium text-tron-muted">Haupt-Agenten</h2>
        <div className="grid gap-4 sm:grid-cols-2">
          {agents.map((a) => (
            <div key={a.id} className="tron-panel p-6">
              <div className="flex items-center gap-2">
                <span className="font-medium text-tron-accent">{a.name}</span>
                <span className="rounded bg-tron-accent/20 px-1.5 py-0.5 text-xs text-tron-muted">
                  {a.source === "openclaw" ? "OpenClaw (Telegram)" : "Operator (Agent-System)"}
                </span>
              </div>
              {a.description != null && (
                <p className="mt-2 text-sm text-tron-text">{a.description}</p>
              )}
              {a.details != null && (
                <p className="mt-1 text-sm text-tron-muted">{a.details}</p>
              )}
            </div>
          ))}
        </div>
      </section>

      <section>
        <h2 className="mb-4 text-lg font-medium text-tron-muted">Captain’s Workflows (Planner, Critic, Factory, …)</h2>
        <div className="tron-panel overflow-hidden">
          <div className="overflow-x-auto">
            <table className="w-full min-w-[480px] text-sm">
              <thead>
                <tr className="border-b border-tron-accent/20 text-left text-tron-muted">
                  <th className="p-3">Name</th>
                  <th className="p-3">ID</th>
                  <th className="p-3">Beschreibung</th>
                </tr>
              </thead>
              <tbody>
                {workflows.map((w) => (
                  <tr key={w.id} className="border-b border-tron-accent/10 hover:bg-tron-accent/5">
                    <td className="p-3 font-medium text-tron-accent">{w.name}</td>
                    <td className="p-3 font-mono text-tron-dim">{w.id}</td>
                    <td className="p-3 text-tron-text">{w.description}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
        {workflows.length === 0 && (
          <p className="text-sm text-tron-dim">Keine Workflows gefunden.</p>
        )}
      </section>
    </div>
  );
}
