import { readdir, readFile } from "fs/promises";
import path from "path";
import { OPERATOR_ROOT } from "@/lib/operator/config";

const CLIENTS_PATH = path.join(OPERATOR_ROOT, "factory", "clients");

export const dynamic = "force-dynamic";

export default async function ClientsPage() {
  let files: string[] = [];
  try {
    files = await readdir(CLIENTS_PATH);
  } catch {
    //
  }
  const clients: Array<{ name: string; data: Record<string, unknown> }> = [];
  for (const f of files) {
    if (!f.endsWith(".json")) continue;
    try {
      const raw = await readFile(path.join(CLIENTS_PATH, f), "utf-8");
      clients.push({ name: f.replace(".json", ""), data: JSON.parse(raw) as Record<string, unknown> });
    } catch {
      //
    }
  }
  return (
    <div className="space-y-6">
      <h1 className="text-3xl font-bold tracking-tight text-tron-text">
        Kunden & Zielgruppen (Clients)
      </h1>
      <p className="max-w-xl text-sm text-tron-muted">
        Hier verwaltest du Profile deiner Zielgruppen, nach denen das System (Factory) sucht.
      </p>
      <div className="grid gap-4 sm:grid-cols-2 mt-4">
        {clients.map((c) => (
          <div key={c.name} className="tron-panel p-6">
            <h2 className="mb-3 font-medium text-tron-accent">{c.name}</h2>
            <pre className="max-h-48 overflow-auto rounded border border-tron-accent/20 bg-tron-bg p-3 font-mono text-xs text-tron-text">
              {JSON.stringify(c.data, null, 2)}
            </pre>
          </div>
        ))}
      </div>
      {clients.length === 0 && (
        <div className="tron-panel p-8 text-center text-tron-dim">
          Keine Client-Konfigurationen in factory/clients gefunden.
        </div>
      )}
    </div>
  );
}
