"use client";

import { useEffect, useState } from "react";
import Link from "next/link";

type Entry = {
  ts: string;
  from: string;
  to: string;
  plan: string;
  request?: string;
  overall?: string;
  recommendation?: string;
  atlas_overall?: string;
  atlas_recommendation?: string;
  run_dir?: string;
};

function formatTs(ts: string): string {
  try {
    const d = new Date(ts);
    return d.toLocaleString(undefined, { dateStyle: "short", timeStyle: "short" });
  } catch {
    return ts;
  }
}

export default function AgentActivityPage() {
  const [entries, setEntries] = useState<Entry[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    fetch("/api/agent-activity")
      .then((r) => r.json())
      .then((data) => {
        if (cancelled) return;
        if (data.entries) setEntries(data.entries);
        if (data.error) setError(data.error);
      })
      .catch((e) => {
        if (!cancelled) setError(String(e));
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, []);

  return (
    <div className="space-y-6 animate-fade-in">
      <div className="flex flex-wrap items-end justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold tracking-tight" style={{ color: "var(--tron-text)" }}>
            Agent Activity
          </h1>
          <p className="mt-1 max-w-xl text-sm" style={{ color: "var(--tron-text-muted)" }}>
            Wer hat wen beauftragt und was kam zurück: June → ARGUS → ATLAS. Einträge entstehen bei jeder Delegation (june-delegate-argus, argus-delegate-atlas).
          </p>
        </div>
        <Link
          href="/agents"
          className="text-sm font-medium underline hover:no-underline"
          style={{ color: "var(--tron-accent)" }}
        >
          ← Agents & Workflows
        </Link>
      </div>

      {loading && (
        <p className="text-sm" style={{ color: "var(--tron-text-muted)" }}>
          Lade …
        </p>
      )}
      {error && (
        <p className="rounded-lg border border-red-500/50 bg-red-500/10 px-4 py-2 text-sm text-red-600 dark:text-red-400">
          {error}
        </p>
      )}
      {!loading && !error && entries.length === 0 && (
        <div
          className="rounded-xl border border-dashed py-12 text-center"
          style={{ borderColor: "var(--tron-border)", color: "var(--tron-text-dim)" }}
        >
          Noch keine Einträge. Sobald June an ARGUS oder ARGUS an ATLAS delegiert, erscheinen sie hier.
        </div>
      )}
      {!loading && entries.length > 0 && (
        <ul className="space-y-4">
          {entries.map((e, i) => (
            <li
              key={`${e.ts}-${e.from}-${e.to}-${i}`}
              className="rounded-xl border p-4"
              style={{
                borderColor: "var(--tron-border)",
                background: "var(--tron-bg-panel)",
              }}
            >
              <div className="flex flex-wrap items-center gap-2 text-sm">
                <span style={{ color: "var(--tron-text-dim)" }}>{formatTs(e.ts)}</span>
                <span className="font-semibold capitalize" style={{ color: "var(--tron-accent)" }}>
                  {e.from}
                </span>
                <span style={{ color: "var(--tron-text-dim)" }}>→</span>
                <span className="font-semibold capitalize" style={{ color: "var(--tron-text)" }}>
                  {e.to}
                </span>
                <span
                  className="rounded px-2 py-0.5 text-xs font-medium"
                  style={{
                    background: "color-mix(in srgb, var(--tron-accent) 15%, transparent)",
                    color: "var(--tron-text)",
                  }}
                >
                  {e.plan}
                </span>
              </div>
              {e.request && (
                <p className="mt-1.5 text-sm" style={{ color: "var(--tron-text-muted)" }}>
                  Request: {e.request.length > 120 ? `${e.request.slice(0, 120)}…` : e.request}
                </p>
              )}
              <div className="mt-2 flex flex-wrap gap-3 text-xs" style={{ color: "var(--tron-text-dim)" }}>
                {e.overall && (
                  <span>
                    OVERALL=<strong style={{ color: e.overall === "PASS" ? "var(--tron-success, #22c55e)" : "var(--tron-text)" }}>{e.overall}</strong>
                  </span>
                )}
                {e.recommendation && <span>RECOMMENDATION={e.recommendation}</span>}
                {e.atlas_overall && (
                  <span>
                    ATLAS_OVERALL=<strong style={{ color: e.atlas_overall === "PASS" ? "var(--tron-success, #22c55e)" : "var(--tron-text)" }}>{e.atlas_overall}</strong>
                  </span>
                )}
                {e.atlas_recommendation && <span>ATLAS_REC={e.atlas_recommendation}</span>}
              </div>
              {e.run_dir && (
                <p className="mt-1 font-mono text-[11px]" style={{ color: "var(--tron-text-dim)" }}>
                  {e.run_dir}
                </p>
              )}
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
