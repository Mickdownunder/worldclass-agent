"use client";

import { useEffect, useState } from "react";

interface Step {
  ts: string;
  step: string;
  duration_s: number;
}

interface ProgressData {
  alive?: boolean;
  heartbeat?: string;
  phase?: string;
  step?: string;
  step_index?: number;
  step_total?: number;
  steps_completed?: Step[];
  started_at?: string;
}

export function ActivityFeed({ projectId }: { projectId: string }) {
  const [progress, setProgress] = useState<ProgressData | null>(null);
  const [isRunning, setIsRunning] = useState<boolean>(false);

  useEffect(() => {
    let mounted = true;
    
    const poll = async () => {
      try {
        const res = await fetch(`/api/research/${projectId}/progress`);
        if (res.ok) {
          const data = await res.json();
          if (mounted) {
            setIsRunning(!!data.is_running);
            setProgress(data.data);
          }
        }
      } catch (e) {
        // ignore
      }
    };

    poll();
    const interval = setInterval(poll, 3000);
    return () => {
      mounted = false;
      clearInterval(interval);
    };
  }, [projectId]);

  if (!progress || (!isRunning && (!progress.steps_completed || progress.steps_completed.length === 0))) {
    return null;
  }

  // Display current step at top, then recent completed steps below
  const stepsCompleted = progress.steps_completed || [];
  // reverse to show newest first
  const reversedSteps = [...stepsCompleted].reverse().slice(0, 5);

  return (
    <div
      className="rounded-lg mb-6 overflow-hidden"
      style={{ border: "1px solid var(--tron-border)", background: "var(--tron-bg-panel)" }}
    >
      <div className="px-5 py-3 flex items-center justify-between" style={{ borderBottom: "1px solid var(--tron-border)" }}>
        <span className="text-[11px] font-semibold uppercase tracking-wider" style={{ color: "var(--tron-text-muted)" }}>
          Live Activity Feed
        </span>
        <span className="font-mono text-[10px]" style={{ color: "var(--tron-text-dim)" }}>
          Phase: {progress.phase || "—"}
        </span>
      </div>
      
      <div className="p-4 space-y-3">
        {isRunning && progress.step && (
          <div className="flex items-center gap-3">
            <span
              className="h-2 w-2 shrink-0 rounded-full animate-pulse"
              style={{ background: "var(--tron-accent)" }}
            />
            <span className="text-sm font-mono" style={{ color: "var(--tron-text)" }}>
              {progress.step}
            </span>
            {progress.step_total ? (
              <span className="text-xs font-mono ml-auto" style={{ color: "var(--tron-text-dim)" }}>
                [{progress.step_index}/{progress.step_total}]
              </span>
            ) : null}
          </div>
        )}
        
        {!isRunning && progress.step === "Done" && (
          <div className="flex items-center gap-3">
            <span
              className="h-2 w-2 shrink-0 rounded-full"
              style={{ background: "var(--tron-success)" }}
            />
            <span className="text-sm font-mono" style={{ color: "var(--tron-success)" }}>
              Phase completed
            </span>
          </div>
        )}

        {reversedSteps.length > 0 && (
          <div className="pt-2 mt-2 space-y-2" style={{ borderTop: "1px dashed color-mix(in srgb, var(--tron-border) 50%, transparent)" }}>
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
      </div>
    </div>
  );
}