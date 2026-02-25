import Link from "next/link";
import { listPacks } from "@/lib/operator/packs";

export const dynamic = "force-dynamic";

export default async function PacksPage() {
  const packs = await listPacks();
  return (
    <div className="space-y-6">
      <h1 className="text-3xl font-bold tracking-tight text-tron-text">
        Ergebnisse & Packs
      </h1>
      <p className="max-w-xl text-sm text-tron-muted">
        Packs sind gebündelte Ergebnisse aus dem Factory Cycle (z. B. aufbereitete Leads, Reports) für deine Kunden oder Zielgruppen.
      </p>
      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3 mt-4">
        {packs.map((p) => (
          <Link
            key={`${p.client}-${p.date}`}
            href={`/packs/${p.client}/${p.date}`}
            className="tron-panel block p-4 transition hover:border-tron-accent/50 hover:shadow-[0_0_24px_var(--tron-glow)]"
          >
            <div className="font-medium text-tron-accent">{p.client}</div>
            <div className="text-sm text-tron-muted">{p.date}</div>
          </Link>
        ))}
      </div>
      {packs.length === 0 && (
        <div className="tron-panel p-8 text-center text-tron-dim">
          Noch keine Packs. Führe einen Factory Cycle aus, um Packs zu erzeugen.
        </div>
      )}
    </div>
  );
}
