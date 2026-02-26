"use client";

import { useEffect, useRef } from "react";
import { useRouter } from "next/navigation";

interface LiveRefreshProps {
  /** When true, refresh the current route data on interval (e.g. re-fetch server component data). */
  enabled: boolean;
  /** Polling interval in ms. Default 6000. */
  intervalMs?: number;
  /** If true, show a small "Live" indicator when refreshing. */
  showIndicator?: boolean;
}

/**
 * Calls router.refresh() on an interval while enabled, so server-rendered data
 * (e.g. Execution Pipeline, Running Jobs, project status) updates without manual reload.
 */
export function LiveRefresh({
  enabled,
  intervalMs = 6000,
  showIndicator = true,
}: LiveRefreshProps) {
  const router = useRouter();
  const intervalRef = useRef<ReturnType<typeof setInterval> | null>(null);

  useEffect(() => {
    if (!enabled) {
      if (intervalRef.current) {
        clearInterval(intervalRef.current);
        intervalRef.current = null;
      }
      return;
    }
    intervalRef.current = setInterval(() => {
      router.refresh();
    }, intervalMs);
    return () => {
      if (intervalRef.current) {
        clearInterval(intervalRef.current);
        intervalRef.current = null;
      }
    };
  }, [enabled, intervalMs, router]);

  if (!enabled || !showIndicator) return null;

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
