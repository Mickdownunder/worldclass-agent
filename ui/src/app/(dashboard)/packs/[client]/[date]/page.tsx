import Link from "next/link";
import { getPack } from "@/lib/operator/packs";
import { notFound } from "next/navigation";

export const dynamic = "force-dynamic";

export default async function PackDetailPage({
  params,
}: { params: Promise<{ client: string; date: string }> }) {
  const { client, date } = await params;
  const pack = await getPack(client, date);
  if (!pack) notFound();
  return (
    <div className="space-y-6">
      <div className="flex items-center gap-4">
        <Link href="/packs" className="text-tron-accent hover:underline">
          ← Packs
        </Link>
        <h1 className="text-3xl font-bold tracking-tight text-tron-text">
          {client} — {date}
        </h1>
      </div>
      {pack.summaryMd != null && (
        <div className="tron-panel p-6">
          <h2 className="mb-4 text-sm font-medium text-tron-muted">Summary</h2>
          <div className="prose prose-invert max-w-none text-tron-text prose-headings:text-tron-accent prose-p:text-tron-muted">
            <pre className="whitespace-pre-wrap font-sans text-sm">{pack.summaryMd}</pre>
          </div>
        </div>
      )}
      {pack.packJson != null && (
        <div className="tron-panel p-6">
          <h2 className="mb-4 text-sm font-medium text-tron-muted">Pack data</h2>
          <pre className="max-h-96 overflow-auto rounded border border-tron-accent/20 bg-tron-bg p-4 font-mono text-xs text-tron-text">
            {JSON.stringify(pack.packJson, null, 2)}
          </pre>
        </div>
      )}
      {!pack.summaryMd && !pack.packJson && (
        <p className="text-tron-dim">Kein Inhalt für diesen Pack.</p>
      )}
    </div>
  );
}
