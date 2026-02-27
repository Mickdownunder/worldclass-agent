"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { BrainRiverFlow } from "@/components/BrainRiverFlow";
import { BrainProcessBar } from "@/components/BrainProcessBar";
import { LoadingSpinner } from "@/components/LoadingSpinner";
import { ConfirmDialog } from "@/components/ConfirmDialog";
import type { BrainStatus } from "@/lib/operator/health";

interface TracePhase {
  phase?: string;
  reasoning?: string;
  decision?: string;
  confidence?: number;
  ts?: string;
  trace_id?: string;
}

interface Props {
  latestTrace: TracePhase[];
  totalCycles: number;
  totalReflections: number;
  avgQuality: number;
  brain: BrainStatus | null;
}

export function BrainRiverFlowWrapper({
  latestTrace: initialTrace,
  totalCycles: initialCycles,
  totalReflections: initialReflections,
  avgQuality: initialQuality,
  brain: initialBrain,
}: Props) {
  const [trace, setTrace] = useState<TracePhase[]>(initialTrace);
  const [totalCycles, setTotalCycles] = useState(initialCycles);
  const [totalReflections, setTotalReflections] = useState(initialReflections);
  const [avgQuality, setAvgQuality] = useState(initialQuality);
  const [brain, setBrain] = useState<BrainStatus | null>(initialBrain);

  const [cycleRunning, setCycleRunning] = useState(false);
  const [polling, setPolling] = useState(false);
  const [showConfirm, setShowConfirm] = useState(false);
  const [message, setMessage] = useState("");

  const pollRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const cycleStartTraceRef = useRef<string | null>(null);

  const fetchStatus = useCallback(async () => {
    try {
      const res = await fetch("/api/brain-cycle-status");
      if (!res.ok) return;
      const data = await res.json();
      if (data.latestTrace) setTrace(data.latestTrace);
      if (data.totalCycles != null) setTotalCycles(data.totalCycles);
      if (data.totalReflections != null) setTotalReflections(data.totalReflections);
      if (data.avgQuality != null) setAvgQuality(data.avgQuality);
      if (data.brain !== undefined) setBrain(data.brain);

      if (polling) {
        const phases = (data.latestTrace as TracePhase[]).map(
          (t: TracePhase) => t.phase?.toLowerCase(),
        );
        const latestTraceId = (data.latestTrace as TracePhase[])[0]?.trace_id;

        const hasNewTrace =
          cycleStartTraceRef.current &&
          latestTraceId &&
          latestTraceId !== cycleStartTraceRef.current;
        const hasReflect = phases.includes("reflect");

        if (hasNewTrace && hasReflect) {
          stopPolling();
          setCycleRunning(false);
          setMessage("Cycle abgeschlossen");
          setTimeout(() => setMessage(""), 4000);
        }
      }
    } catch {
      // silent
    }
  }, [polling]);

  function stopPolling() {
    setPolling(false);
    if (pollRef.current) {
      clearInterval(pollRef.current);
      pollRef.current = null;
    }
  }

  function startPolling() {
    stopPolling();
    setPolling(true);
    pollRef.current = setInterval(() => {
      fetchStatus();
    }, 3000);
  }

  useEffect(() => {
    return () => {
      if (pollRef.current) clearInterval(pollRef.current);
    };
  }, []);

  useEffect(() => {
    if (polling) {
      if (pollRef.current) clearInterval(pollRef.current);
      pollRef.current = setInterval(fetchStatus, 3000);
    }
  }, [polling, fetchStatus]);

  async function startCycle() {
    setCycleRunning(true);
    setMessage("");
    setShowConfirm(false);

    cycleStartTraceRef.current = trace[0]?.trace_id ?? null;

    setTrace([]);

    try {
      const res = await fetch("/api/actions/brain-cycle", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          goal: "Decide and execute the most impactful next action",
        }),
      });
      const data = await res.json();
      if (data.ok) {
        setMessage("Cycle gestartet — Live-Tracking aktiv");
        startPolling();
        setTimeout(() => fetchStatus(), 1500);
      } else {
        setMessage(data.error ?? "Fehler beim Starten");
        setCycleRunning(false);
      }
    } catch (e) {
      setMessage(String((e as Error).message));
      setCycleRunning(false);
    }
  }

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between gap-3 flex-wrap">
        <div className="flex-1 min-w-0" />
        <div className="flex items-center gap-3">
          {polling && (
            <div className="flex items-center gap-1.5">
              <span
                className="inline-block w-2 h-2 rounded-full"
                style={{ background: "#22c55e", animation: "pulse-live 1.5s ease-in-out infinite" }}
              />
              <span className="text-[10px] font-semibold" style={{ color: "#22c55e" }}>
                LIVE
              </span>
            </div>
          )}
          {message && (
            <span className="text-[11px]" style={{ color: "var(--tron-text-muted)" }}>
              {message}
            </span>
          )}
          <button
            onClick={() => cycleRunning ? undefined : setShowConfirm(true)}
            disabled={cycleRunning}
            className="px-4 py-2 rounded-lg text-xs font-bold transition-all"
            style={{
              background: cycleRunning
                ? "var(--tron-border)"
                : "linear-gradient(135deg, #8b5cf6, #3b82f6)",
              color: "#fff",
              opacity: cycleRunning ? 0.6 : 1,
            }}
          >
            {cycleRunning ? (
              <span className="flex items-center gap-2">
                <LoadingSpinner className="inline-block w-3 h-3" /> Cycle läuft…
              </span>
            ) : (
              "🧠 Brain Cycle starten"
            )}
          </button>
          {!polling && !cycleRunning && (
            <button
              onClick={fetchStatus}
              className="px-3 py-2 rounded-lg text-xs transition-all"
              style={{
                background: "var(--tron-bg-panel)",
                color: "var(--tron-text-muted)",
                border: "1px solid var(--tron-border)",
              }}
              title="Daten neu laden"
            >
              ↻
            </button>
          )}
        </div>
      </div>

      <BrainRiverFlow
        latestTrace={trace}
        totalCycles={totalCycles}
        totalReflections={totalReflections}
        avgQuality={avgQuality}
      />
      <BrainProcessBar brain={brain} />

      {showConfirm && (
        <ConfirmDialog
          open
          title="Brain Cycle starten?"
          message="Ein neuer Cognitive Cycle wird gestartet. Die Phasen werden live in der River-Visualisierung angezeigt."
          confirmLabel="Starten"
          cancelLabel="Abbrechen"
          variant="primary"
          onConfirm={startCycle}
          onCancel={() => setShowConfirm(false)}
        />
      )}

      <style>{`
        @keyframes pulse-live {
          0%, 100% { opacity: 1; }
          50% { opacity: 0.3; }
        }
      `}</style>
    </div>
  );
}
