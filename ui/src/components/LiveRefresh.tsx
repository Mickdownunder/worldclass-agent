"use client";

import { useEffect, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import type { ProgressApiResponse, RuntimeState } from "@/lib/operator/progress";
import { RuntimeStateBadge } from "@/components/RuntimeStateBadge";

interface LiveRefreshProps {
  enabled: boolean;
  intervalMs?: number;
  showIndicator?: boolean;
  projectId?: string;
}

/**
 * Polls progress API and shows deterministic runtime state (RUNNING/IDLE/STUCK/ERROR_LOOP/FAILED/DONE).
 * Also triggers router.refresh() so server-rendered data stays in sync.
 */
export function LiveRefresh({
  enabled,
  intervalMs = 6000,
  showIndicator = true,
  projectId,
}: LiveRefreshProps) {
  const router = useRouter();
  const intervalRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const [progress, setProgress] = useState<ProgressApiResponse | null>(null);

  useEffect(() => {
    if (!enabled) {
      setProgress(null);
      if (intervalRef.current) {
        clearInterval(intervalRef.current);
        intervalRef.current = null;
      }
      return;
    }

    const pollProgress = async () => {
      if (projectId) {
        try {
          const res = await fetch(`/api/research/projects/${projectId}/progress`);
          if (res.ok) {
            const data = (await res.json()) as ProgressApiResponse;
            setProgress(data);
          }
        } catch {
          setProgress(null);
        }
      }
      router.refresh();
    };

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

  const state = (progress?.state ?? "IDLE") as RuntimeState;
  const step = progress?.step ?? progress?.data?.step ?? null;

  return (
    <RuntimeStateBadge
      state={state}
      step={step}
      pulse={state === "RUNNING"}
    />
  );
}
