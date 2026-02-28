"use client";

import { useEffect, useState } from "react";

function formatElapsed(from: string, to?: string | number): string {
  if (!from) return "—";
  try {
    const start = new Date(from).getTime();
    const end = typeof to === "number" ? to : (to ? new Date(to).getTime() : Date.now());
    const ms = end - start;
    if (ms < 0) return "0s";
    if (ms < 60_000) return `${Math.floor(ms / 1000)}s`;
    if (ms < 3_600_000) return `${Math.floor(ms / 60_000)}m ${Math.floor((ms % 60_000) / 1000)}s`;
    return `${Math.floor(ms / 3_600_000)}h ${Math.floor((ms % 3_600_000) / 60_000)}m`;
  } catch {
    return "—";
  }
}

interface LiveElapsedTimerProps {
  created_at: string;
  completed_at?: string | null;
  isActive: boolean;
  className?: string;
  style?: React.CSSProperties;
}

/**
 * Shows runtime elapsed. When isActive, updates every second for a live tick.
 * Uses mounted guard so server and client render the same initial value (avoids hydration mismatch).
 */
export function LiveElapsedTimer({
  created_at,
  completed_at,
  isActive,
  className,
  style,
}: LiveElapsedTimerProps) {
  const [mounted, setMounted] = useState(false);
  const [now, setNow] = useState(0);

  useEffect(() => {
    setMounted(true);
  }, []);

  useEffect(() => {
    if (!mounted || !isActive) return;
    setNow(Date.now());
    const t = setInterval(() => setNow(Date.now()), 1000);
    return () => clearInterval(t);
  }, [mounted, isActive]);

  const end = isActive ? (mounted ? now : created_at) : completed_at;
  return (
    <span className={className} style={{ fontVariantNumeric: "tabular-nums", ...style }}>
      {formatElapsed(created_at, end)}
    </span>
  );
}
