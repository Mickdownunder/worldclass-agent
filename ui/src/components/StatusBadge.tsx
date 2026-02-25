"use client";

type StatusVariant =
  | "active"
  | "done"
  | "failed"
  | "explore"
  | "focus"
  | "connect"
  | "verify"
  | "synthesize"
  | "running"
  | "unknown";

const variantStyles: Record<
  StatusVariant,
  { bg: string; text: string; border: string }
> = {
  active: { bg: "bg-white/10", text: "text-white", border: "border-white/20" },
  done: { bg: "bg-tron-success/10", text: "text-tron-success", border: "border-tron-success/20" },
  failed: { bg: "bg-tron-error/10", text: "text-tron-error", border: "border-tron-error/20" },
  explore: { bg: "bg-white/5", text: "text-tron-text", border: "border-white/10" },
  focus: { bg: "bg-white/5", text: "text-tron-text", border: "border-white/10" },
  connect: { bg: "bg-white/5", text: "text-tron-text", border: "border-white/10" },
  verify: { bg: "bg-white/5", text: "text-tron-text", border: "border-white/10" },
  synthesize: { bg: "bg-white/5", text: "text-tron-text", border: "border-white/10" },
  running: { bg: "bg-white/10", text: "text-white", border: "border-white/20" },
  unknown: { bg: "bg-white/5", text: "text-tron-muted", border: "border-white/10" },
};

function toVariant(value: string): StatusVariant {
  const lower = value.toLowerCase();
  if (["active", "done", "failed", "explore", "focus", "connect", "verify", "synthesize", "running", "unknown"].includes(lower))
    return lower as StatusVariant;
  if (["done", "completed", "success"].some((s) => lower.includes(s))) return "done";
  if (["fail", "error"].some((s) => lower.includes(s))) return "failed";
  if (["run", "pending"].some((s) => lower.includes(s))) return "running";
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
  return (
    <span
      className={`inline-flex items-center rounded-full border px-2.5 py-0.5 text-[11px] font-medium tracking-wide uppercase ${style.bg} ${style.text} ${style.border} ${className}`}
    >
      {label ?? status}
    </span>
  );
}
