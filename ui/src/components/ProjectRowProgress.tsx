"use client";

import { useEffect, useState } from "react";
import type { ProgressApiResponse, RuntimeState } from "@/lib/operator/progress";
import { RuntimeStateBadge } from "@/components/RuntimeStateBadge";

interface ProjectRowProgressProps {
  projectId: string;
  isActive: boolean;
  status: string;
  progressPercent: number;
}

export function ProjectRowProgress({
  projectId,
  isActive,
  status,
  progressPercent,
}: ProjectRowProgressProps) {
  const [progress, setProgress] = useState<ProgressApiResponse | null>(null);

  useEffect(() => {
    if (!isActive) return;

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
    const interval = setInterval(poll, 5000);
    return () => {
      mounted = false;
      clearInterval(interval);
    };
  }, [projectId, isActive]);

  const state = (progress?.state ?? "IDLE") as RuntimeState;
  const step = progress?.step ?? progress?.data?.step ?? null;

  return (
    <div className="mt-1.5 flex items-center gap-2 flex-wrap">
      <div
        className="h-0.5 w-24 overflow-hidden rounded-full shrink-0"
        style={{ background: "var(--tron-border)" }}
      >
        <div
          className="h-full rounded-full transition-all"
          style={{
            width: `${progressPercent}%`,
            background:
              status === "done"
                ? "var(--tron-success)"
                : status === "failed"
                  ? "var(--tron-error)"
                  : "var(--tron-accent)",
          }}
        />
      </div>
      <span className="text-[9px] font-mono shrink-0" style={{ color: "var(--tron-text-dim)" }}>
        {progressPercent}%
      </span>

      {isActive && (
        <div
          className="flex items-center gap-1.5 ml-2 border-l pl-2"
          style={{ borderColor: "var(--tron-border)" }}
        >
          <RuntimeStateBadge state={state} step={step} pulse={state === "RUNNING"} />
        </div>
      )}
    </div>
  );
}
