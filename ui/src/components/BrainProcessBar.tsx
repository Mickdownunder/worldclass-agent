"use client";

import { useState } from "react";
import type { BrainStatus } from "@/lib/operator/health";

interface Props {
  brain?: BrainStatus | null;
}

export function BrainProcessBar({ brain }: Props) {
  const [killing, setKilling] = useState(false);
  const [message, setMessage] = useState<string | null>(null);

  if (!brain) return null;
  const cycleCount = brain.cycle?.count ?? 0;
  const reflectCount = brain.reflect?.count ?? 0;
  if (cycleCount + reflectCount === 0) return null;

  const anyStuck = brain.cycle?.stuck || brain.reflect?.stuck;
  const maxElapsed = Math.max(brain.cycle?.max_elapsed_sec ?? 0, brain.reflect?.max_elapsed_sec ?? 0);

  function formatElapsed(sec: number): string {
    if (sec < 60) return `${sec}s`;
    if (sec < 3600) return `${Math.round(sec / 60)} min`;
    return `${(sec / 3600).toFixed(1)} h`;
  }

  async function killBrain() {
    setKilling(true);
    setMessage(null);
    try {
      const res = await fetch("/api/actions/brain-kill", { method: "POST" });
      const data = await res.json();
      setMessage(data.ok ? "Brain-Prozesse beendet." : data.error ?? "Fehler.");
    } catch (e) {
      setMessage(String((e as Error).message));
    } finally {
      setKilling(false);
      setTimeout(() => setMessage(null), 4000);
    }
  }

  return (
    <div
      className="rounded-lg px-4 py-3 flex flex-wrap items-center gap-3 text-[12px]"
      style={{
        background: anyStuck
          ? "linear-gradient(90deg, rgba(245,158,11,0.06), rgba(236,72,153,0.04))"
          : "linear-gradient(90deg, rgba(139,92,246,0.06), rgba(59,130,246,0.04))",
        border: `1px solid ${anyStuck ? "rgba(245,158,11,0.35)" : "rgba(139,92,246,0.2)"}`,
      }}
    >
      <div className="flex items-center gap-2">
        <span
          className="inline-block w-2 h-2 rounded-full"
          style={{
            background: anyStuck ? "#f59e0b" : "#8b5cf6",
            animation: !anyStuck ? "pulse-glow-sm 2s ease-in-out infinite" : "none",
          }}
        />
        <span className="font-semibold" style={{ color: anyStuck ? "#f59e0b" : "var(--tron-text)" }}>
          Brain {anyStuck ? "hängend" : "aktiv"}
        </span>
      </div>

      <div className="flex items-center gap-3 font-mono" style={{ color: "var(--tron-text-muted)" }}>
        {cycleCount > 0 && (
          <span>{cycleCount} Cycle{cycleCount > 1 ? "s" : ""}</span>
        )}
        {reflectCount > 0 && (
          <span>{reflectCount} Reflect{reflectCount > 1 ? "s" : ""}</span>
        )}
        {maxElapsed > 0 && (
          <span style={{ color: anyStuck ? "#f59e0b" : "var(--tron-text-dim)" }}>
            längster: {formatElapsed(maxElapsed)}
          </span>
        )}
      </div>

      {anyStuck && (
        <button
          onClick={killBrain}
          disabled={killing}
          className="ml-auto rounded px-3 py-1.5 text-[11px] font-semibold transition-colors disabled:opacity-50"
          style={{
            background: "rgba(245,158,11,0.15)",
            border: "1px solid rgba(245,158,11,0.4)",
            color: "#f59e0b",
          }}
        >
          {killing ? "Beende…" : "Prozesse beenden"}
        </button>
      )}
      {message && (
        <span className="text-[11px]" style={{ color: "var(--tron-text-dim)" }}>
          {message}
        </span>
      )}

      <style>{`
        @keyframes pulse-glow-sm {
          0%, 100% { box-shadow: 0 0 4px rgba(139,92,246,0.3); }
          50% { box-shadow: 0 0 10px rgba(139,92,246,0.7); }
        }
      `}</style>
    </div>
  );
}
