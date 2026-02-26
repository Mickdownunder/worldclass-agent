"use client";

import { useEffect, useState } from "react";

interface ProjectRowProgressProps {
  projectId: string;
  isActive: boolean;
  status: string;
  progressPercent: number;
}

export function ProjectRowProgress({ projectId, isActive, status, progressPercent }: ProjectRowProgressProps) {
  const [isRunning, setIsRunning] = useState<boolean>(false);
  const [stepText, setStepText] = useState<string>("");

  useEffect(() => {
    if (!isActive) return;

    let mounted = true;
    const poll = async () => {
      try {
        const res = await fetch(`/api/research/${projectId}/progress`);
        if (res.ok) {
          const data = await res.json();
          if (mounted) {
            setIsRunning(!!data.is_running);
            if (data.data?.step) {
              setStepText(data.data.step);
            }
          }
        }
      } catch (e) {
        // ignore
      }
    };

    poll();
    const interval = setInterval(poll, 6000);
    return () => {
      mounted = false;
      clearInterval(interval);
    };
  }, [projectId, isActive]);

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
            background: status === "done"
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
        <div className="flex items-center gap-1.5 ml-2 border-l pl-2" style={{ borderColor: "var(--tron-border)" }}>
          {isRunning ? (
            <>
              <span
                className="h-1.5 w-1.5 shrink-0 rounded-full animate-pulse"
                style={{ background: "var(--tron-accent)" }}
              />
              <span className="text-[10px] font-mono truncate max-w-[200px]" style={{ color: "var(--tron-accent)" }}>
                Running{stepText ? `: ${stepText}` : ""}
              </span>
            </>
          ) : (
            <>
              <span className="h-1.5 w-1.5 shrink-0 rounded-full bg-muted-foreground/40" />
              <span className="text-[10px] font-mono text-muted-foreground">Idle</span>
            </>
          )}
        </div>
      )}
    </div>
  );
}