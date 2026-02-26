"use client";

export function ReliabilityBar({ score }: { score: number }) {
  const pct = Math.round(score * 100);
  const color = score >= 0.75 ? "#22c55e" : score >= 0.5 ? "#f59e0b" : "#f43f5e";
  return (
    <div className="flex items-center gap-2">
      <div className="w-16 h-1.5 rounded-full overflow-hidden" style={{ background: "var(--tron-border)" }}>
        <div className="h-full rounded-full transition-all" style={{ width: `${pct}%`, background: color }} />
      </div>
      <span className="font-mono text-[10px] font-semibold" style={{ color, minWidth: "2.5rem" }}>{pct}%</span>
    </div>
  );
}
