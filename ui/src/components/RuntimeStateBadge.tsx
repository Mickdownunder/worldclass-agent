"use client";

import type { RuntimeState } from "@/lib/operator/progress";
import { RUNTIME_STATE_LABELS, RUNTIME_STATE_HINT } from "@/lib/operator/progress";

interface RuntimeStateBadgeProps {
  state: RuntimeState;
  step?: string | null;
  pulse?: boolean;
  className?: string;
}

const STATE_STYLES: Record<
  RuntimeState,
  { bg: string; border: string; color: string; dot?: string }
> = {
  RUNNING: {
    bg: "color-mix(in srgb, var(--tron-accent) 12%, transparent)",
    border: "color-mix(in srgb, var(--tron-accent) 30%, transparent)",
    color: "var(--tron-accent)",
    dot: "var(--tron-accent)",
  },
  IDLE: {
    bg: "var(--tron-bg)",
    border: "var(--tron-border)",
    color: "var(--tron-text-muted)",
    dot: "var(--tron-text-dim)",
  },
  STUCK: {
    bg: "color-mix(in srgb, #f59e0b 15%, transparent)",
    border: "color-mix(in srgb, #f59e0b 40%, transparent)",
    color: "#f59e0b",
    dot: "#f59e0b",
  },
  ERROR_LOOP: {
    bg: "color-mix(in srgb, var(--tron-error) 15%, transparent)",
    border: "color-mix(in srgb, var(--tron-error) 40%, transparent)",
    color: "var(--tron-error)",
    dot: "var(--tron-error)",
  },
  FAILED: {
    bg: "color-mix(in srgb, var(--tron-error) 12%, transparent)",
    border: "color-mix(in srgb, var(--tron-error) 30%, transparent)",
    color: "var(--tron-error)",
    dot: "var(--tron-error)",
  },
  DONE: {
    bg: "color-mix(in srgb, var(--tron-success) 12%, transparent)",
    border: "color-mix(in srgb, var(--tron-success) 30%, transparent)",
    color: "var(--tron-success)",
    dot: "var(--tron-success)",
  },
};

export function RuntimeStateBadge({
  state,
  step,
  pulse = state === "RUNNING",
  className = "",
}: RuntimeStateBadgeProps) {
  const style = STATE_STYLES[state];
  const label = RUNTIME_STATE_LABELS[state];
  const title = RUNTIME_STATE_HINT[state] + (step ? ` — ${step}` : "");

  return (
    <span
      className={`inline-flex items-center gap-1.5 rounded px-2 py-0.5 text-[11px] font-medium transition-colors ${className}`}
      style={{
        background: style.bg,
        border: `1px solid ${style.border}`,
        color: style.color,
      }}
      title={title}
    >
      <span
        className={`h-1.5 w-1.5 shrink-0 rounded-full ${pulse ? "animate-pulse" : ""}`}
        style={{ background: style.dot ?? style.color }}
      />
      {label}
      {step && state === "RUNNING" && (
        <span className="truncate max-w-[180px]" style={{ opacity: 0.95 }}>
          : {step}
        </span>
      )}
    </span>
  );
}
