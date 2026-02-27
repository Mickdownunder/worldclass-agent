"use client";

interface ExecutionTreeProps {
  currentPhase: string;
  status: string;
  phaseHistory?: string[];
  phaseTimings?: Record<
    string,
    { started_at: string; completed_at: string; duration_s: number }
  >;
}

const PHASES = [
  { id: "explore",   label: "Explore",   desc: "Source discovery" },
  { id: "focus",     label: "Focus",     desc: "Relevance filtering" },
  { id: "connect",   label: "Connect",   desc: "Cross-referencing" },
  { id: "verify",    label: "Verify",    desc: "Fact-checking" },
  { id: "synthesize",label: "Synthesize",desc: "Report generation" },
];

type PhaseStatus = "done" | "active" | "pending" | "failed";

function isTerminalStatus(status: string): boolean {
  return status === "done" || status === "cancelled" || status === "abandoned" || status.startsWith("failed");
}

function getPhaseStatus(phaseId: string, currentPhase: string, projectStatus: string): PhaseStatus {
  if (projectStatus === "done") return "done";
  const isFailed = isTerminalStatus(projectStatus) && projectStatus !== "done";
  const currentIdx = PHASES.findIndex((p) => p.id === currentPhase);
  const phaseIdx = PHASES.findIndex((p) => p.id === phaseId);
  if (isFailed) {
    if (phaseIdx < currentIdx) return "done";
    if (phaseIdx === currentIdx) return "failed";
    return "pending";
  }
  if (phaseIdx < currentIdx) return "done";
  if (phaseIdx === currentIdx) return "active";
  return "pending";
}

const phaseColors: Record<PhaseStatus, { node: string; text: string; connector: string }> = {
  done:    { node: "bg-emerald-500/20 border-emerald-500/50 text-emerald-400",    text: "text-emerald-400",    connector: "bg-emerald-500/40" },
  active:  { node: "bg-blue-500/20 border-blue-500/70 text-blue-300",             text: "text-blue-300",       connector: "bg-[var(--tron-border)]" },
  failed:  { node: "bg-red-500/20 border-red-500/50 text-red-400",                text: "text-red-400",        connector: "bg-red-500/30" },
  pending: { node: "bg-[var(--tron-panel-hover)] border-[var(--tron-border)] text-[var(--tron-text-dim)]", text: "text-[var(--tron-text-dim)]", connector: "bg-[var(--tron-border)]" },
};

export function ExecutionTree({
  currentPhase,
  status,
  phaseHistory,
  phaseTimings,
}: ExecutionTreeProps) {
  return (
    <div className="w-full overflow-x-auto pb-1">
      <div className="flex items-start gap-0 min-w-max">
        {PHASES.map((phase, idx) => {
          const phaseStatus = getPhaseStatus(phase.id, currentPhase, status);
          const colors = phaseColors[phaseStatus];
          const isLast = idx === PHASES.length - 1;

          return (
            <div key={phase.id} className="flex items-start">
              {/* Phase node */}
              <div className="flex flex-col items-center gap-1.5" style={{ minWidth: 80 }}>
                {/* Circle */}
                <div
                  className={`flex h-8 w-8 items-center justify-center rounded-full border-2 text-[11px] font-bold transition-all ${colors.node}`}
                >
                  {phaseStatus === "done" ? (
                    <svg width="12" height="12" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
                      <polyline points="2,6 5,9 10,3" />
                    </svg>
                  ) : phaseStatus === "failed" ? (
                    <svg width="12" height="12" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round">
                      <line x1="3" y1="3" x2="9" y2="9" />
                      <line x1="9" y1="3" x2="3" y2="9" />
                    </svg>
                  ) : phaseStatus === "active" ? (
                    <span className="w-2 h-2 rounded-full bg-blue-400 animate-pulse" />
                  ) : (
                    <span className="text-[9px] font-mono font-bold">{idx + 1}</span>
                  )}
                </div>

                {/* Labels */}
                <div className="flex flex-col items-center gap-0.5 text-center" style={{ minWidth: 72 }}>
                  <span className={`text-[11px] font-semibold ${colors.text}`}>
                    {phase.label}
                  </span>
                  <span className="text-[9px] font-mono leading-tight" style={{ color: "var(--tron-text-dim)" }}>
                    {phase.desc}
                  </span>
                  {phaseTimings?.[phase.id] && (
                    <span className="text-[9px] font-mono" style={{ color: "var(--tron-text-dim)" }}>
                      {phaseTimings[phase.id].duration_s < 60
                        ? `${Math.round(phaseTimings[phase.id].duration_s)}s`
                        : `${(phaseTimings[phase.id].duration_s / 60).toFixed(1)}m`}
                    </span>
                  )}
                  {phaseStatus === "active" && (
                    <span className="text-[9px] font-mono font-bold px-1.5 py-0.5 rounded"
                      style={{ background: "rgba(68,117,243,0.15)", color: "var(--tron-accent)" }}>
                      ACTIVE
                    </span>
                  )}
                  {phaseStatus === "failed" && (
                    <span className="text-[9px] font-mono font-bold px-1.5 py-0.5 rounded"
                      style={{ background: "rgba(239,68,68,0.15)", color: "rgb(248,113,113)" }}>
                      FAILED
                    </span>
                  )}
                </div>
              </div>

              {/* Connector line */}
              {!isLast && (
                <div className="flex items-center" style={{ marginTop: 15, width: 32 }}>
                  <div className={`h-px w-full transition-all ${phaseStatus === "done" ? "bg-emerald-500/40" : "bg-[var(--tron-border)]"}`} />
                  <svg width="6" height="8" className="shrink-0" fill={phaseStatus === "done" ? "rgba(34,197,94,0.5)" : "var(--tron-border)"}>
                    <polygon points="0,0 6,4 0,8" />
                  </svg>
                </div>
              )}
            </div>
          );
        })}

        {/* Done terminal node */}
        <div className="flex items-start">
          <div className="flex items-center" style={{ marginTop: 15, width: 32 }}>
            <div className={`h-px w-full ${status === "done" ? "bg-emerald-500/40" : "bg-[var(--tron-border)]"}`} />
            <svg width="6" height="8" className="shrink-0" fill={status === "done" ? "rgba(34,197,94,0.5)" : "var(--tron-border)"}>
              <polygon points="0,0 6,4 0,8" />
            </svg>
          </div>
          <div className="flex flex-col items-center gap-1.5" style={{ minWidth: 56 }}>
            <div className={`flex h-8 w-8 items-center justify-center rounded-full border-2 text-[11px] font-bold transition-all ${status === "done" ? "bg-emerald-500/20 border-emerald-500/50 text-emerald-400" : "bg-[var(--tron-panel-hover)] border-[var(--tron-border)] text-[var(--tron-text-dim)]"}`}>
              {status === "done" ? (
                <svg width="12" height="12" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round">
                  <path d="M2 6h8M6 2l4 4-4 4" />
                </svg>
              ) : "→"}
            </div>
            <span className={`text-[11px] font-semibold ${status === "done" ? "text-emerald-400" : "text-[var(--tron-text-dim)]"}`}>
              Done
            </span>
          </div>
        </div>
      </div>
    </div>
  );
}
