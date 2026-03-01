import Link from "next/link";
import { DiscoveryProjectForm } from "@/components/DiscoveryProjectForm";

export const dynamic = "force-dynamic";

export default function DiscoveryResearchPage() {
  return (
    <div className="space-y-6 animate-fade-in">
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div>
          <div className="flex items-center gap-2 text-sm mb-1">
            <Link
              href="/research"
              className="font-medium transition-colors hover:underline"
              style={{ color: "var(--tron-text-muted)" }}
            >
              ← Research
            </Link>
          </div>
          <h1 className="text-xl font-semibold tracking-tight" style={{ color: "var(--tron-text)" }}>
            Discovery Research
          </h1>
          <p className="mt-1 text-sm" style={{ color: "var(--tron-text-muted)" }}>
            Eigenes Menü und eigener Ablauf: Breite vor Tiefe, Hypothesen, Lücken, Novel Connections. Alle Phasen (Explore, Focus, Connect, Verify, Synthesize) laufen im Discovery-Modus anders.
          </p>
        </div>
      </div>

      <div
        className="rounded-lg"
        style={{ border: "1px solid var(--tron-border)", background: "var(--tron-bg-panel)" }}
      >
        <div className="px-4 py-3" style={{ borderBottom: "1px solid var(--tron-border)" }}>
          <span className="text-[11px] font-semibold uppercase tracking-wider" style={{ color: "var(--tron-text-muted)" }}>
            Neues Discovery-Projekt
          </span>
        </div>
        <div className="px-4 py-4">
          <DiscoveryProjectForm />
        </div>
      </div>

      <div className="text-[12px]" style={{ color: "var(--tron-text-dim)" }}>
        <p className="font-medium mb-1">Unterschiede zu Standard/Frontier:</p>
        <ul className="list-disc list-inside space-y-0.5 ml-1">
          <li>Evidence Gate: kein verified_claim-Check; Pass bei Breite (Findings/Sources).</li>
          <li>Conductor: search_more vor read_more, verify spät, synthesize bei 8+ Domains, 20+ Findings.</li>
          <li>Nach Verify: Discovery Analysis (novel_connections, emerging_concepts, research_frontier, key_hypothesis).</li>
          <li>Report & Critic: Novelty 3× gewichtet; 0.5 mit hoher Novelty besser als 0.7 ohne neue Insights.</li>
        </ul>
      </div>
    </div>
  );
}
