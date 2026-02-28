"use client";

import { LoadingSpinner } from "@/components/LoadingSpinner";
import type { Critique } from "../types";

interface CritiqueTabProps {
  critique: Critique | null;
  loading: boolean;
}

function scoreColor(score: number): string {
  if (score >= 0.7) return "var(--tron-success)";
  if (score >= 0.5) return "var(--tron-warning)";
  return "var(--tron-error, #e53e3e)";
}

export function CritiqueTab({ critique, loading }: CritiqueTabProps) {
  if (loading) return <LoadingSpinner />;
  if (!critique) {
    return (
      <div className="py-10 text-center">
        <p className="text-sm" style={{ color: "var(--tron-text-muted)" }}>
          No critique yet.
        </p>
        <p className="mt-1 text-xs" style={{ color: "var(--tron-text-dim)" }}>
          Complete the Synthesize phase and run the critic to see weaknesses and suggestions.
        </p>
      </div>
    );
  }

  const { score, weaknesses, suggestions, strengths } = critique;

  return (
    <div className="space-y-6">
      <div className="flex items-center gap-4 flex-wrap">
        <div
          className="rounded-lg border px-4 py-3 min-w-[120px] text-center"
          style={{
            borderColor: "var(--tron-border)",
            background: "var(--tron-bg-panel)",
          }}
        >
          <div className="text-[11px] font-semibold uppercase tracking-wider" style={{ color: "var(--tron-text-muted)" }}>
            Score
          </div>
          <div className="mt-1 text-2xl font-bold font-mono" style={{ color: scoreColor(score) }}>
            {score.toFixed(2)}
          </div>
          {critique.pass != null && (
            <div className="mt-0.5 text-[10px]" style={{ color: "var(--tron-text-dim)" }}>
              {critique.pass ? "Pass" : "Below threshold"}
            </div>
          )}
        </div>
      </div>

      {weaknesses.length > 0 && (
        <section>
          <h3 className="text-xs font-semibold uppercase tracking-wider mb-2" style={{ color: "var(--tron-error, #e53e3e)" }}>
            Weaknesses
          </h3>
          <ul className="space-y-2 list-disc list-inside text-sm" style={{ color: "var(--tron-text)" }}>
            {weaknesses.map((w, i) => (
              <li key={i} className="border-l-2 pl-3 py-0.5" style={{ borderColor: "var(--tron-error, #e53e3e)" }}>
                {w}
              </li>
            ))}
          </ul>
        </section>
      )}

      {suggestions.length > 0 && (
        <section>
          <h3 className="text-xs font-semibold uppercase tracking-wider mb-2" style={{ color: "var(--tron-accent)" }}>
            Suggestions
          </h3>
          <ul className="space-y-2 list-disc list-inside text-sm" style={{ color: "var(--tron-text)" }}>
            {suggestions.map((s, i) => (
              <li key={i} className="border-l-2 pl-3 py-0.5" style={{ borderColor: "var(--tron-accent)" }}>
                {s}
              </li>
            ))}
          </ul>
        </section>
      )}

      {strengths && strengths.length > 0 && (
        <section>
          <h3 className="text-xs font-semibold uppercase tracking-wider mb-2" style={{ color: "var(--tron-success)" }}>
            Strengths
          </h3>
          <ul className="space-y-2 list-disc list-inside text-sm" style={{ color: "var(--tron-text)" }}>
            {strengths.map((s, i) => (
              <li key={i} className="border-l-2 pl-3 py-0.5" style={{ borderColor: "var(--tron-success)" }}>
                {s}
              </li>
            ))}
          </ul>
        </section>
      )}

      {weaknesses.length === 0 && suggestions.length === 0 && (!strengths || strengths.length === 0) && (
        <p className="text-sm" style={{ color: "var(--tron-text-muted)" }}>
          No detailed feedback in this critique.
        </p>
      )}
    </div>
  );
}
