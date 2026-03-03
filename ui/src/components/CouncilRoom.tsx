"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { Bot, FileText, CheckCircle2, AlertCircle } from "lucide-react";

const COUNCIL_POLL_MS = 4000;

interface CouncilData {
  log: string;
  brainInjected?: boolean;
  brainError?: string | null;
}

export function CouncilRoom({ projectId, councilStatus, hasMasterDossier }: { projectId: string; councilStatus?: string; hasMasterDossier: boolean }) {
  const router = useRouter();
  const [council, setCouncil] = useState<CouncilData | null>(null);
  const shouldPoll = councilStatus === "active" || councilStatus === "waiting";

  useEffect(() => {
    const fetchCouncil = async () => {
      try {
        const res = await fetch(`/api/research/projects/${encodeURIComponent(projectId)}/council`);
        if (res.ok) {
          const data = (await res.json()) as CouncilData;
          setCouncil(data);
        }
      } catch {
        setCouncil(null);
      }
    };
    fetchCouncil();
    if (shouldPoll) {
      const interval = setInterval(() => {
        fetchCouncil();
        router.refresh();
      }, COUNCIL_POLL_MS);
      return () => clearInterval(interval);
    }
  }, [projectId, shouldPoll, router]);

  if (councilStatus !== "active" && councilStatus !== "done" && councilStatus !== "waiting" && !hasMasterDossier) {
    return null;
  }

  const isMeeting = councilStatus === "active" && !hasMasterDossier;
  const isWaiting = councilStatus === "waiting";
  const logLines = council?.log?.trim().split("\n").filter(Boolean) ?? [];
  const lastLogLines = logLines.slice(-40);

  return (
    <div className="mt-6 rounded-lg overflow-hidden" style={{ border: "1px solid var(--tron-border)", background: "var(--tron-bg-panel)" }}>
      <div className="flex items-center gap-2 px-5 py-3" style={{ borderBottom: "1px solid var(--tron-border)", background: "var(--tron-panel-header)" }}>
        <Bot className={`w-5 h-5 ${isMeeting ? "text-blue-400 animate-pulse" : isWaiting ? "text-amber-400" : "text-emerald-400"}`} />
        <h2 className="text-sm font-semibold uppercase tracking-wider text-tron-text">
          The Research Council
        </h2>
        {isMeeting && (
          <span className="ml-auto text-[11px] font-mono text-blue-400 animate-pulse bg-blue-500/10 px-2 py-0.5 rounded border border-blue-500/25">
            MEETING IN PROGRESS
          </span>
        )}
        {isWaiting && (
          <span className="ml-auto text-[11px] font-mono text-amber-400 bg-amber-500/10 px-2 py-0.5 rounded border border-amber-500/25">
            FIELD AGENTS DEPLOYED
          </span>
        )}
        {hasMasterDossier && (
          <span className="ml-auto text-[11px] font-mono text-emerald-400 bg-emerald-500/10 px-2 py-0.5 rounded border border-emerald-500/25 flex items-center gap-1">
            <CheckCircle2 className="w-3 h-3" /> DOSSIER COMPLETE
          </span>
        )}
      </div>

      <div className="p-6 relative overflow-hidden flex flex-col gap-4 min-h-[120px]">
        {/* Council activity log */}
        {lastLogLines.length > 0 && (
          <div className="rounded border overflow-hidden" style={{ borderColor: "var(--tron-border)", background: "var(--tron-bg)" }}>
            <div className="px-3 py-1.5 text-[10px] font-mono uppercase tracking-wider" style={{ color: "var(--tron-text-dim)", borderBottom: "1px solid var(--tron-border)" }}>
              Council log
            </div>
            <pre className="p-3 text-[11px] font-mono whitespace-pre-wrap break-words max-h-[200px] overflow-y-auto" style={{ color: "var(--tron-text-muted)" }}>
              {lastLogLines.join("\n")}
            </pre>
          </div>
        )}

        {isWaiting ? (
          <div className="relative z-10 flex flex-col items-center gap-4 text-center">
            <div className="flex items-center justify-center w-16 h-16 rounded-full bg-amber-500/20 border border-amber-500/50 mb-2">
              <Bot className="w-8 h-8 text-amber-400 animate-pulse" />
            </div>
            <h3 className="text-sm font-bold text-amber-400">Waiting for next generation...</h3>
            <p className="text-xs text-tron-text-muted max-w-md">
              The PI has evaluated the initial findings and autonomously dispatched a new wave of field agents to test specific hypotheses in the sandbox.
            </p>
          </div>
        ) : isMeeting ? (
          <div className="relative z-10 flex flex-col items-center gap-6">
            <div className="flex items-center gap-8">
              <div className="flex flex-col items-center gap-2 animate-bounce" style={{ animationDelay: "0ms", animationDuration: "2s" }}>
                <div className="w-10 h-10 rounded-full bg-indigo-500/20 border border-indigo-500/50 flex items-center justify-center">
                  <Bot className="w-5 h-5 text-indigo-400" />
                </div>
                <span className="text-[10px] font-mono text-indigo-400">Agent A</span>
              </div>
              <div className="flex flex-col items-center gap-2 z-10">
                <div className="w-16 h-16 rounded-lg bg-blue-500/20 border-2 border-blue-400 shadow-[0_0_15px_rgba(59,130,246,0.5)] flex items-center justify-center relative overflow-hidden">
                  <div className="absolute inset-0 bg-blue-400/20 animate-pulse" />
                  <Bot className="w-8 h-8 text-blue-400" />
                </div>
                <span className="text-xs font-bold font-mono text-blue-400 tracking-wider">PI AGENT</span>
              </div>
              <div className="flex flex-col items-center gap-2 animate-bounce" style={{ animationDelay: "500ms", animationDuration: "2s" }}>
                <div className="w-10 h-10 rounded-full bg-violet-500/20 border border-violet-500/50 flex items-center justify-center">
                  <Bot className="w-5 h-5 text-violet-400" />
                </div>
                <span className="text-[10px] font-mono text-violet-400">Agent B</span>
              </div>
            </div>
            <p className="text-sm font-mono text-tron-text-muted max-w-lg text-center leading-relaxed">
              Principal Investigator is cross-pollinating findings and sandbox experiments from all field agents to synthesize the Master Dossier...
            </p>
          </div>
        ) : hasMasterDossier ? (
          <div className="relative z-10 flex flex-col items-center gap-4 text-center">
            <div className="w-16 h-16 rounded-full bg-emerald-500/20 border border-emerald-500/50 flex items-center justify-center mb-2 shadow-[0_0_20px_rgba(16,185,129,0.2)]">
              <FileText className="w-8 h-8 text-emerald-400" />
            </div>
            <h3 className="text-lg font-bold text-tron-text">Bundle Synthesis Dossier Ready</h3>
            <p className="text-sm text-tron-text-muted max-w-md">
              The Research Council has concluded its review. Theory and sandbox experiments have been merged into a final Master Dossier.
            </p>
            {council?.brainInjected === true && (
              <div className="mt-2 text-xs font-mono text-tron-accent bg-tron-accent/10 px-3 py-1.5 rounded-full border border-tron-accent/30">
                Brain updated with new principles.
              </div>
            )}
            {council?.brainError && (
              <div className="mt-2 flex items-center gap-2 text-xs font-mono text-red-400 bg-red-500/10 px-3 py-2 rounded border border-red-500/30 max-w-md">
                <AlertCircle className="w-4 h-4 shrink-0" />
                <span>Brain update failed: {council.brainError}</span>
              </div>
            )}
          </div>
        ) : null}
      </div>
    </div>
  );
}
