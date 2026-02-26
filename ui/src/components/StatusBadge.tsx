"use client";

type StatusVariant =
  | "active"
  | "done"
  | "failed"
  | "failed_insufficient_evidence"
  | "explore"
  | "focus"
  | "connect"
  | "verify"
  | "verifying"
  | "synthesize"
  | "running"
  | "pending"
  | "unknown";

const variantStyles: Record<StatusVariant, { bg: string; text: string; border: string; dot?: string }> = {
  active:                      { bg: "bg-blue-500/10",   text: "text-blue-400",   border: "border-blue-500/25",  dot: "bg-blue-400" },
  done:                        { bg: "bg-emerald-500/10",text: "text-emerald-400",border: "border-emerald-500/25" },
  failed:                      { bg: "bg-rose-500/10",   text: "text-rose-400",   border: "border-rose-500/25" },
  failed_insufficient_evidence:{ bg: "bg-rose-500/10",   text: "text-rose-400",   border: "border-rose-500/25" },
  verifying:                   { bg: "bg-amber-500/10",  text: "text-amber-400",  border: "border-amber-500/25", dot: "bg-amber-400" },
  verify:                      { bg: "bg-amber-500/10",  text: "text-amber-400",  border: "border-amber-500/25", dot: "bg-amber-400" },
  running:                     { bg: "bg-blue-500/10",   text: "text-blue-400",   border: "border-blue-500/25",  dot: "bg-blue-400" },
  pending:                     { bg: "bg-slate-500/10",  text: "text-slate-400",  border: "border-slate-500/20" },
  explore:                     { bg: "bg-indigo-500/10", text: "text-indigo-400", border: "border-indigo-500/20", dot: "bg-indigo-400" },
  focus:                       { bg: "bg-violet-500/10", text: "text-violet-400", border: "border-violet-500/20", dot: "bg-violet-400" },
  connect:                     { bg: "bg-cyan-500/10",   text: "text-cyan-400",   border: "border-cyan-500/20",   dot: "bg-cyan-400" },
  synthesize:                  { bg: "bg-teal-500/10",   text: "text-teal-400",   border: "border-teal-500/20",   dot: "bg-teal-400" },
  unknown:                     { bg: "bg-slate-500/10",  text: "text-slate-500",  border: "border-slate-700/30" },
};

const ACTIVE_STATUSES = new Set(["active", "running", "explore", "focus", "connect", "verify", "verifying", "synthesize"]);

const DISPLAY_LABELS: Record<string, string> = {
  failed_insufficient_evidence: "FAILED · INSUFF. EVIDENCE",
  verifying: "VERIFYING",
  synthesize: "SYNTHESIZE",
  explore: "EXPLORE",
  focus: "FOCUS",
  connect: "CONNECT",
  verify: "VERIFY",
  running: "RUNNING",
  active: "ACTIVE",
  done: "DONE",
  failed: "FAILED",
  pending: "PENDING",
  unknown: "UNKNOWN",
};

function toVariant(value: string): StatusVariant {
  const lower = value.toLowerCase().replace(/[-\s]/g, "_");
  if (lower in variantStyles) return lower as StatusVariant;
  if (lower.includes("failed_insufficient") || lower.includes("insufficient"))
    return "failed_insufficient_evidence";
  if (lower.includes("fail") || lower.includes("error")) return "failed";
  if (lower.includes("verif")) return "verifying";
  if (lower.includes("done") || lower.includes("completed") || lower.includes("success"))
    return "done";
  if (lower.includes("run") || lower.includes("active")) return "running";
  if (lower.includes("pending")) return "pending";
  return "unknown";
}

export function StatusBadge({
  status,
  label,
  className = "",
}: {
  status: string;
  label?: string;
  className?: string;
}) {
  const variant = toVariant(status);
  const style = variantStyles[variant];
  const showDot = !!style.dot && ACTIVE_STATUSES.has(variant);
  const displayLabel = label ?? (DISPLAY_LABELS[variant] ?? status.toUpperCase());

  return (
    <span
      className={`inline-flex items-center gap-1.5 rounded border px-2 py-0.5 text-[10px] font-bold tracking-[0.08em] uppercase font-mono ${style.bg} ${style.text} ${style.border} ${className}`}
    >
      {showDot && (
        <span className={`w-1.5 h-1.5 rounded-full shrink-0 ${style.dot} animate-pulse`} />
      )}
      {displayLabel}
    </span>
  );
}
