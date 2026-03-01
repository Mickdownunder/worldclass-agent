"use client";

import { useEffect, useState } from "react";
import { Bot, FileText, CheckCircle2 } from "lucide-react";

export function CouncilRoom({ projectId, councilStatus, hasMasterDossier }: { projectId: string; councilStatus?: string; hasMasterDossier: boolean }) {
  if (councilStatus !== "active" && councilStatus !== "done" && !hasMasterDossier) {
    return null;
  }

  const isMeeting = councilStatus === "active" && !hasMasterDossier;

  return (
    <div className="mt-6 rounded-lg overflow-hidden" style={{ border: "1px solid var(--tron-border)", background: "var(--tron-bg-panel)" }}>
      <div className="flex items-center gap-2 px-5 py-3" style={{ borderBottom: "1px solid var(--tron-border)", background: "var(--tron-panel-header)" }}>
        <Bot className={`w-5 h-5 ${isMeeting ? "text-blue-400 animate-pulse" : "text-emerald-400"}`} />
        <h2 className="text-sm font-semibold uppercase tracking-wider text-tron-text">
          The Research Council
        </h2>
        {isMeeting && (
          <span className="ml-auto text-[11px] font-mono text-blue-400 animate-pulse bg-blue-500/10 px-2 py-0.5 rounded border border-blue-500/25">
            MEETING IN PROGRESS
          </span>
        )}
        {hasMasterDossier && (
          <span className="ml-auto text-[11px] font-mono text-emerald-400 bg-emerald-500/10 px-2 py-0.5 rounded border border-emerald-500/25 flex items-center gap-1">
            <CheckCircle2 className="w-3 h-3" /> DOSSIER COMPLETE
          </span>
        )}
      </div>

      <div className="p-6 relative overflow-hidden flex flex-col items-center justify-center min-h-[160px]">
        {/* Animated Background Grid */}
        <div className="absolute inset-0 opacity-[0.03]" style={{ backgroundImage: "linear-gradient(var(--tron-text) 1px, transparent 1px), linear-gradient(90deg, var(--tron-text) 1px, transparent 1px)", backgroundSize: "20px 20px" }} />
        
        {isMeeting ? (
          <div className="relative z-10 flex flex-col items-center gap-6">
            <div className="flex items-center gap-8">
              {/* Agent 1 */}
              <div className="flex flex-col items-center gap-2 animate-bounce" style={{ animationDelay: "0ms", animationDuration: "2s" }}>
                <div className="w-10 h-10 rounded-full bg-indigo-500/20 border border-indigo-500/50 flex items-center justify-center">
                  <Bot className="w-5 h-5 text-indigo-400" />
                </div>
                <span className="text-[10px] font-mono text-indigo-400">Agent A</span>
              </div>
              
              {/* PI Agent */}
              <div className="flex flex-col items-center gap-2 z-10">
                <div className="w-16 h-16 rounded-lg bg-blue-500/20 border-2 border-blue-400 shadow-[0_0_15px_rgba(59,130,246,0.5)] flex items-center justify-center relative overflow-hidden">
                  <div className="absolute inset-0 bg-blue-400/20 animate-pulse" />
                  <Bot className="w-8 h-8 text-blue-400" />
                </div>
                <span className="text-xs font-bold font-mono text-blue-400 tracking-wider">PI AGENT</span>
              </div>
              
              {/* Agent 2 */}
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
            <div className="mt-2 text-xs font-mono text-tron-accent bg-tron-accent/10 px-3 py-1.5 rounded-full border border-tron-accent/30">
              Brain updated with new principles.
            </div>
          </div>
        ) : null}
      </div>
    </div>
  );
}
