"use client";

import { useEffect, useRef, useState } from "react";
import { useRouter } from "next/navigation";

interface LiveRefreshProps {
  /** When true, refresh the current route data on interval (e.g. re-fetch server component data). */
  enabled: boolean;
  /** Polling interval in ms. Default 6000. */
  intervalMs?: number;
  /** If true, show a small "Live" indicator when refreshing. */
  showIndicator?: boolean;
  /** Optional project ID. If provided, polls progress.json for "Running" vs "Idle" status. */
  projectId?: string;
}

/**
 * Calls router.refresh() on an interval while enabled, so server-rendered data
 * (e.g. Execution Pipeline, Running Jobs, project status) updates without manual reload.
 */
export function LiveRefresh({
  enabled,
  intervalMs = 6000,
  showIndicator = true,
  projectId,
}: LiveRefreshProps) {
  const router = useRouter();
  const intervalRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const [isRunning, setIsRunning] = useState<boolean>(false);
  const [stepText, setStepText] = useState<string>("");

  useEffect(() => {
    if (!enabled) {
      setIsRunning(false);
      if (intervalRef.current) {
        clearInterval(intervalRef.current);
        intervalRef.current = null;
      }
      return;
    }

    const pollProgress = async () => {
      if (projectId) {
        try {
          const res = await fetch(`/api/research/${projectId}/progress`);
          if (res.ok) {
            const data = await res.json();
            setIsRunning(!!data.is_running);
            if (data.data?.step) {
              setStepText(data.data.step);
            }
          }
        } catch (e) {
          setIsRunning(false);
        }
      }
      router.refresh();
    };

    // Initial call
    pollProgress();

    intervalRef.current = setInterval(pollProgress, intervalMs);
    
    return () => {
      if (intervalRef.current) {
        clearInterval(intervalRef.current);
        intervalRef.current = null;
      }
    };
  }, [enabled, intervalMs, router, projectId]);

  if (!enabled || !showIndicator) return null;

  // If no projectId is passed, we fall back to a generic "Live" or just don't show the advanced indicator.
  // The plan said: 'remove always-on Live label'.
  if (!projectId) {
    return (
      <span
        className="inline-flex items-center gap-1.5 rounded px-2 py-0.5 text-[10px] font-medium"
        style={{
          background: "color-mix(in srgb, var(--tron-accent) 12%, transparent)",
          border: "1px solid color-mix(in srgb, var(--tron-accent) 30%, transparent)",
          color: "var(--tron-accent)",
        }}
        title="Seite aktualisiert sich automatisch"
      >
        <span
          className="h-1.5 w-1.5 shrink-0 rounded-full animate-pulse"
          style={{ background: "var(--tron-accent)" }}
        />
        Live
      </span>
    );
  }

  if (isRunning) {
    return (
      <span
        className="inline-flex items-center gap-1.5 rounded px-2 py-0.5 text-[11px] font-medium transition-colors"
        style={{
          background: "color-mix(in srgb, var(--tron-accent) 12%, transparent)",
          border: "1px solid color-mix(in srgb, var(--tron-accent) 30%, transparent)",
          color: "var(--tron-accent)",
        }}
        title="Prozess läuft"
      >
        <span
          className="h-1.5 w-1.5 shrink-0 rounded-full animate-pulse"
          style={{ background: "var(--tron-accent)" }}
        />
        {stepText || "Running"}
      </span>
    );
  }

  return (
    <span
      className="inline-flex items-center gap-1.5 rounded px-2 py-0.5 text-[11px] font-medium text-muted-foreground border border-border bg-muted/30 transition-colors"
      title="Projekt aktiv, aber aktuell kein Prozess"
    >
      <span className="h-1.5 w-1.5 shrink-0 rounded-full bg-muted-foreground/40" />
      Idle
    </span>
  );
}