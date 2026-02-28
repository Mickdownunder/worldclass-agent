"use client";

import { useEffect, useState } from "react";
import type { ProgressApiResponse, RuntimeState } from "@/lib/operator/progress";
import { RuntimeStateBadge } from "@/components/RuntimeStateBadge";
import { RUNTIME_STATE_HINT } from "@/lib/operator/progress";

interface Step {
  ts: string;
  step: string;
  duration_s: number;
}

export function ActivityFeed({
  projectId,
  currentPhase,
  isProjectActive,
}: {
  projectId: string;
  currentPhase?: string;
  isProjectActive?: boolean;
}) {
  const [progress, setProgress] = useState<ProgressApiResponse | null>(null);

  useEffect(() => {
    let mounted = true;
    const poll = async () => {
      try {
        const res = await fetch(`/api/research/projects/${projectId}/progress`);
        if (res.ok && mounted) {
          setProgress((await res.json()) as ProgressApiResponse);
        }
      } catch {
        // ignore
      }
    };

    poll();
    const interval = setInterval(poll, 2000);
    return () => {
      mounted = false;
      clearInterval(interval);
    };
  }, [projectId]);

  if (!isProjectActive) return null;

  const state = (progress?.state ?? "IDLE") as RuntimeState;
  const data = progress?.data;
  const stepsCompleted = (data?.steps_completed ?? []) as Step[];
  const readingSourceRe = /Reading source (\d+)\/(\d+)/;
  const sortedSteps = [...stepsCompleted].sort((a, b) => {
    const ma = a.step.match(readingSourceRe);
    const mb = b.step.match(readingSourceRe);
    if (ma && mb) {
      const totalA = parseInt(ma[2], 10);
      const totalB = parseInt(mb[2], 10);
      if (totalA !== totalB) return totalA - totalB;
      return parseInt(ma[1], 10) - parseInt(mb[1], 10);
    }
    if (ma) return 1;
    if (mb) return -1;
    return new Date(a.ts).getTime() - new Date(b.ts).getTime();
  });
  const reversedSteps = sortedSteps.slice(-8).reverse();
  const displayPhase = data?.phase ?? currentPhase ?? "—";
  const step = progress?.step ?? data?.step;
  const lastError = progress?.last_error;
  const stuckReason = progress?.stuck_reason;
  const loopSignature = progress?.loop_signature;
  const heartbeatAgeS = progress?.heartbeat_age_s;
  const events = progress?.events ?? [];

  const hasProgressData = progress && (state !== "IDLE" || stepsCompleted.length > 0);

  function formatTs(iso: string): string {
    try {
      return new Intl.DateTimeFormat("de-DE", {
        hour: "2-digit",
        minute: "2-digit",
        second: "2-digit",
      }).format(new Date(iso));
    } catch {
      return iso;
    }
  }

  return (
    <div
      className="rounded-lg mb-6 overflow-hidden"
      style={{
        border: "1px solid var(--tron-border)",
        background: "var(--tron-bg-panel)",
      }}
    >
      <div
        className="px-5 py-3 flex items-center justify-between flex-wrap gap-2"
        style={{ borderBottom: "1px solid var(--tron-border)" }}
      >
        <span
          className="text-[11px] font-semibold uppercase tracking-wider"
          style={{ color: "var(--tron-text-muted)" }}
        >
          Live Activity
        </span>
        <div className="flex items-center gap-2">
          <span className="font-mono text-[10px] uppercase" style={{ color: "var(--tron-text-dim)" }}>
            Phase: {displayPhase}
          </span>
          <RuntimeStateBadge state={state} step={step} pulse={state === "RUNNING"} />
        </div>
      </div>

      <div className="p-4 space-y-4">
        {/* State hint */}
        <p className="text-[11px] font-mono" style={{ color: "var(--tron-text-dim)" }} title={RUNTIME_STATE_HINT[state]}>
          {RUNTIME_STATE_HINT[state]}
          {heartbeatAgeS != null && state === "RUNNING" && (
            <> · Letzte Aktivität vor {Math.round(heartbeatAgeS)}s</>
          )}
          {stuckReason && (
            <> · {stuckReason}</>
          )}
        </p>

        {/* Current step */}
        {(state === "RUNNING" || (step && step !== "Done")) && step && (
          <div className="flex items-center gap-3">
            <span
              className="h-2 w-2 shrink-0 rounded-full animate-pulse"
              style={{ background: "var(--tron-accent)" }}
            />
            <span className="text-sm font-mono" style={{ color: "var(--tron-text)" }}>
              {step}
            </span>
            {data?.step_total != null && (
              <span className="text-xs font-mono ml-auto" style={{ color: "var(--tron-text-dim)" }}>
                [{data.step_index ?? 0}/{data.step_total}]
              </span>
            )}
          </div>
        )}

        {/* Error card */}
        {lastError && (
          <div
            className="rounded-md px-3 py-2 border"
            style={{
              background: "color-mix(in srgb, var(--tron-error) 10%, transparent)",
              borderColor: "color-mix(in srgb, var(--tron-error) 40%, transparent)",
            }}
          >
            <div className="text-[11px] font-semibold uppercase tracking-wider" style={{ color: "var(--tron-error)" }}>
              Letzter Fehler {loopSignature ? `(Loop: ${loopSignature})` : ""}
            </div>
            <div className="font-mono text-[11px] mt-1" style={{ color: "var(--tron-text)" }}>
              {lastError.code}: {lastError.message}
            </div>
            <div className="text-[10px] mt-1" style={{ color: "var(--tron-text-dim)" }}>
              {formatTs(lastError.at)}
            </div>
            {(state === "ERROR_LOOP" || state === "STUCK") && (
              <p className="text-[11px] mt-2" style={{ color: "var(--tron-text-muted)" }}>
                → Nächste Phase starten oder Abbrechen, um zu reagieren.
              </p>
            )}
          </div>
        )}

        {/* Phase completed */}
        {state !== "RUNNING" && hasProgressData && step === "Done" && (
          <div className="flex items-center gap-3">
            <span className="h-2 w-2 shrink-0 rounded-full" style={{ background: "var(--tron-success)" }} />
            <span className="text-sm font-mono" style={{ color: "var(--tron-success)" }}>
              Phase abgeschlossen
            </span>
          </div>
        )}

        {/* Idle / no data */}
        {state === "IDLE" && !hasProgressData && (
          <div className="space-y-1">
            <div className="flex items-center gap-3">
              <span
                className="h-2 w-2 shrink-0 rounded-full animate-pulse"
                style={{ background: "var(--tron-accent)" }}
              />
              <span className="text-sm font-mono" style={{ color: "var(--tron-text-muted)" }}>
                {currentPhase ? `Phase ${currentPhase.toUpperCase()} wartet auf Start` : "Warte auf Start…"}
              </span>
            </div>
          </div>
        )}

        {/* Completed steps */}
        {reversedSteps.length > 0 && (
          <div
            className="pt-2 mt-2 space-y-2"
            style={{ borderTop: "1px dashed color-mix(in srgb, var(--tron-border) 50%, transparent)" }}
          >
            <span className="text-[10px] font-semibold uppercase" style={{ color: "var(--tron-text-dim)" }}>
              Abgeschlossene Schritte
            </span>
            {reversedSteps.map((s, i) => (
              <div key={i} className="flex items-start gap-3">
                <span className="text-xs font-mono mt-0.5" style={{ color: "var(--tron-text-dim)", minWidth: "45px" }}>
                  {s.duration_s}s
                </span>
                <span className="text-xs font-mono" style={{ color: "var(--tron-text-muted)" }}>
                  {s.step}
                </span>
              </div>
            ))}
          </div>
        )}

        {/* Event timeline (recent) */}
        {events.length > 0 && (
          <div
            className="pt-2 mt-2 space-y-1"
            style={{ borderTop: "1px dashed color-mix(in srgb, var(--tron-border) 50%, transparent)" }}
          >
            <span className="text-[10px] font-semibold uppercase" style={{ color: "var(--tron-text-dim)" }}>
              Ereignisse
            </span>
            <div className="max-h-32 overflow-y-auto space-y-1">
              {[...events].reverse().slice(0, 15).map((e, i) => (
                <div key={i} className="flex items-center gap-2 text-[10px] font-mono">
                  <span style={{ color: "var(--tron-text-dim)", minWidth: "52px" }}>{formatTs(e.ts)}</span>
                  <span
                    style={{
                      color:
                        e.event === "error"
                          ? "var(--tron-error)"
                          : e.event === "step_started"
                            ? "var(--tron-accent)"
                            : "var(--tron-text-muted)",
                    }}
                  >
                    {e.event}
                    {e.step ? `: ${e.step}` : ""}
                    {e.code ? ` [${e.code}]` : ""}
                  </span>
                </div>
              ))}
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
