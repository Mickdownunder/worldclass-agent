"use client";

import { useState, useEffect, useRef } from "react";

interface PhaseData {
  id: string;
  label: string;
  icon: string;
  color: string;
}

interface TracePhase {
  phase: string;
  reasoning?: string;
  decision?: string;
  confidence?: number;
  ts?: string;
}

interface Props {
  latestTrace: TracePhase[];
  totalCycles: number;
  totalReflections: number;
  avgQuality: number;
}

const PHASES: PhaseData[] = [
  { id: "perceive", label: "Perceive", icon: "👁", color: "#3b82f6" },
  { id: "think",    label: "Think",    icon: "🧠", color: "#8b5cf6" },
  { id: "decide",   label: "Decide",   icon: "⚡", color: "#f59e0b" },
  { id: "act",      label: "Act",      icon: "🚀", color: "#22c55e" },
  { id: "reflect",  label: "Reflect",  icon: "💡", color: "#ec4899" },
];

function getHighestPhaseIndex(tracePhases: TracePhase[]): number {
  let highest = -1;
  for (const t of tracePhases) {
    const idx = PHASES.findIndex((p) => p.id === t.phase?.toLowerCase());
    if (idx > highest) highest = idx;
  }
  return highest;
}

function getPhaseState(
  phaseId: string,
  _tracePhases: TracePhase[],
  highestIndex: number
): "done" | "active" | "idle" {
  const idx = PHASES.findIndex((p) => p.id === phaseId);
  if (idx < 0) return "idle";
  if (idx < highestIndex) return "done";
  if (idx === highestIndex) return "active";
  return "idle";
}

function getPhaseText(phaseId: string, tracePhases: TracePhase[], highestIndex: number): string {
  const found = tracePhases.find((t) => t.phase?.toLowerCase() === phaseId);
  if (found) {
    const r = (found.reasoning || found.decision || "").slice(0, 120);
    return r || "Abgeschlossen";
  }
  const idx = PHASES.findIndex((p) => p.id === phaseId);
  if (idx >= 0 && idx <= highestIndex) return "Abgeschlossen";
  return "Wartet…";
}

function qualityLabel(q: number): { text: string; color: string } {
  if (q <= 0) return { text: "—", color: "var(--tron-text-dim)" };
  if (q >= 0.8) return { text: "Excellent", color: "#22c55e" };
  if (q >= 0.6) return { text: "Good", color: "#22c55e" };
  if (q >= 0.4) return { text: "Fair", color: "#f59e0b" };
  if (q >= 0.2) return { text: "Low", color: "#f43f5e" };
  return { text: "Critical", color: "#f43f5e" };
}

export function BrainRiverFlow({ latestTrace, totalCycles, totalReflections, avgQuality }: Props) {
  const [expandedPhase, setExpandedPhase] = useState<string | null>(null);
  const [animatedIndex, setAnimatedIndex] = useState(-1);
  const prevIndexRef = useRef(-1);

  const targetIndex = getHighestPhaseIndex(latestTrace);

  useEffect(() => {
    if (targetIndex < 0) {
      setAnimatedIndex(-1);
      prevIndexRef.current = -1;
      return;
    }

    const startFrom = targetIndex > prevIndexRef.current
      ? Math.max(prevIndexRef.current, -1)
      : -1;

    if (startFrom < targetIndex) {
      setAnimatedIndex(startFrom);
      let current = startFrom;
      const step = () => {
        current += 1;
        setAnimatedIndex(current);
        if (current < targetIndex) {
          setTimeout(step, 600);
        }
      };
      const timer = setTimeout(step, 300);
      prevIndexRef.current = targetIndex;
      return () => clearTimeout(timer);
    } else {
      setAnimatedIndex(targetIndex);
      prevIndexRef.current = targetIndex;
    }
  }, [targetIndex]);

  const activeIndex = animatedIndex;
  const ql = qualityLabel(avgQuality);

  const RIVER_PATH = "M 60,110 C 150,50 200,170 300,110 C 400,50 450,170 540,110 C 630,50 680,170 760,110 C 840,50 880,170 940,110";

  return (
    <div className="relative">
      {/* Stats row */}
      <div className="flex flex-wrap items-center gap-6 mb-8">
        <div className="flex items-center gap-3">
          <div
            className="w-12 h-12 rounded-full flex items-center justify-center text-2xl"
            style={{
              background: "linear-gradient(135deg, rgba(139,92,246,0.2), rgba(59,130,246,0.2))",
              border: "2px solid rgba(139,92,246,0.4)",
              boxShadow: activeIndex >= 0 ? "0 0 20px rgba(139,92,246,0.3)" : "none",
              animation: activeIndex >= 0 ? "pulse-glow 2s ease-in-out infinite" : "none",
            }}
          >
            🧠
          </div>
          <div>
            <div className="text-lg font-bold" style={{ color: "var(--tron-text)" }}>
              Cognitive Core
            </div>
            <div className="text-[11px]" style={{ color: "var(--tron-text-dim)" }}>
              {activeIndex >= 0 ? `Letzter Cycle: ${PHASES[activeIndex].label}` : "Idle — kein aktiver Cycle"}
            </div>
          </div>
        </div>
        <div className="flex gap-4 ml-auto">
          <div className="text-center">
            <div className="text-xl font-bold font-mono" style={{ color: "var(--tron-accent)" }}>{totalCycles}</div>
            <div className="text-[10px] uppercase tracking-wider" style={{ color: "var(--tron-text-dim)" }}>Cycles</div>
          </div>
          <div className="text-center">
            <div className="text-xl font-bold font-mono" style={{ color: "#ec4899" }}>{totalReflections}</div>
            <div className="text-[10px] uppercase tracking-wider" style={{ color: "var(--tron-text-dim)" }}>Reflections</div>
          </div>
          <div className="text-center">
            <div className="text-xl font-bold font-mono" style={{ color: ql.color }}>
              {ql.text}
            </div>
            <div className="text-[10px] uppercase tracking-wider" style={{ color: "var(--tron-text-dim)" }}>
              {avgQuality > 0 ? `Quality ${(avgQuality * 100).toFixed(0)}%` : "Quality"}
            </div>
          </div>
        </div>
      </div>

      {/* River flow */}
      <div className="relative py-4">
        <svg
          viewBox="0 0 1000 220"
          className="w-full h-auto"
          style={{ filter: "drop-shadow(0 0 6px rgba(59,130,246,0.15))" }}
          preserveAspectRatio="xMidYMid meet"
        >
          <defs>
            <linearGradient id="river-gradient" x1="0%" y1="0%" x2="100%" y2="0%">
              <stop offset="0%" stopColor="#3b82f6" stopOpacity="0.1" />
              <stop offset="25%" stopColor="#8b5cf6" stopOpacity="0.1" />
              <stop offset="50%" stopColor="#f59e0b" stopOpacity="0.1" />
              <stop offset="75%" stopColor="#22c55e" stopOpacity="0.1" />
              <stop offset="100%" stopColor="#ec4899" stopOpacity="0.1" />
            </linearGradient>
            <linearGradient id="river-active" x1="0%" y1="0%" x2="100%" y2="0%">
              <stop offset="0%" stopColor="#3b82f6" stopOpacity="0.6" />
              <stop offset="25%" stopColor="#8b5cf6" stopOpacity="0.6" />
              <stop offset="50%" stopColor="#f59e0b" stopOpacity="0.6" />
              <stop offset="75%" stopColor="#22c55e" stopOpacity="0.6" />
              <stop offset="100%" stopColor="#ec4899" stopOpacity="0.6" />
            </linearGradient>
            <linearGradient id="river-flow" x1="0%" y1="0%" x2="100%" y2="0%">
              <stop offset="0%" stopColor="#3b82f6" />
              <stop offset="25%" stopColor="#8b5cf6" />
              <stop offset="50%" stopColor="#f59e0b" />
              <stop offset="75%" stopColor="#22c55e" />
              <stop offset="100%" stopColor="#ec4899" />
            </linearGradient>
            <filter id="glow">
              <feGaussianBlur stdDeviation="4" result="blur" />
              <feMerge>
                <feMergeNode in="blur" />
                <feMergeNode in="SourceGraphic" />
              </feMerge>
            </filter>
          </defs>

          {/* River bed (full path, dim) */}
          <path d={RIVER_PATH} fill="none" stroke="url(#river-gradient)" strokeWidth="36" strokeLinecap="round" />
          <path d={RIVER_PATH} fill="none" stroke="url(#river-gradient)" strokeWidth="18" strokeLinecap="round" />

          {/* Active river (animated fill) */}
          {activeIndex >= 0 && (
            <>
              <path
                d={RIVER_PATH}
                fill="none"
                stroke="url(#river-active)"
                strokeWidth="18"
                strokeLinecap="round"
                strokeDasharray={`${((activeIndex + 1) / PHASES.length) * 1000} 1000`}
                style={{ transition: "stroke-dasharray 0.8s ease-out" }}
              />
              {/* Flowing particles */}
              <circle r="3" fill="url(#river-flow)" opacity="0.8" filter="url(#glow)">
                <animateMotion dur="4s" repeatCount="indefinite" path={RIVER_PATH} />
              </circle>
              <circle r="2" fill="url(#river-flow)" opacity="0.5">
                <animateMotion dur="4s" repeatCount="indefinite" begin="1.3s" path={RIVER_PATH} />
              </circle>
              <circle r="2.5" fill="url(#river-flow)" opacity="0.6">
                <animateMotion dur="4s" repeatCount="indefinite" begin="2.6s" path={RIVER_PATH} />
              </circle>
            </>
          )}

          {/* Phase nodes */}
          {PHASES.map((phase, i) => {
            const xs = [60, 300, 540, 760, 940];
            const cx = xs[i];
            const cy = 110;
            const state = getPhaseState(phase.id, latestTrace, activeIndex);
            const opacity = state === "idle" ? 0.3 : 1;
            const isActive = state === "active";

            return (
              <g key={phase.id} style={{ cursor: "pointer" }} onClick={() => setExpandedPhase(expandedPhase === phase.id ? null : phase.id)}>
                {isActive && (
                  <circle cx={cx} cy={cy} r="28" fill="none" stroke={phase.color} strokeWidth="2" opacity="0.4">
                    <animate attributeName="r" values="24;32;24" dur="2s" repeatCount="indefinite" />
                    <animate attributeName="opacity" values="0.4;0.1;0.4" dur="2s" repeatCount="indefinite" />
                  </circle>
                )}
                <circle
                  cx={cx}
                  cy={cy}
                  r="22"
                  fill={state !== "idle" ? phase.color : "var(--tron-bg-panel, #0f1218)"}
                  fillOpacity={state !== "idle" ? 0.2 : 0.5}
                  stroke={phase.color}
                  strokeWidth={state !== "idle" ? 2.5 : 1}
                  opacity={opacity}
                  style={{ transition: "opacity 0.5s ease, fill-opacity 0.5s ease, stroke-width 0.3s ease" }}
                />
                {state === "done" && (
                  <text x={cx} y={cy + 1} textAnchor="middle" dominantBaseline="central" fontSize="12" fill={phase.color}>✓</text>
                )}
                {state === "active" && (
                  <circle cx={cx} cy={cy} r="5" fill={phase.color} opacity="0.9">
                    <animate attributeName="r" values="3;6;3" dur="1.5s" repeatCount="indefinite" />
                  </circle>
                )}
                <text
                  x={cx} y={cy + 38} textAnchor="middle" fontSize="11" fontWeight="600"
                  fill={state !== "idle" ? phase.color : "var(--tron-text-dim, #666)"}
                  opacity={opacity} fontFamily="system-ui, sans-serif"
                  style={{ transition: "opacity 0.5s ease" }}
                >
                  {phase.label}
                </text>
                <text x={cx} y={cy - 32} textAnchor="middle" fontSize="18" opacity={opacity}
                  style={{ transition: "opacity 0.5s ease" }}>
                  {phase.icon}
                </text>
              </g>
            );
          })}
        </svg>

        {/* Expanded phase detail */}
        {expandedPhase && (
          <div
            className="mt-2 rounded-lg p-4 text-sm transition-all"
            style={{
              background: "var(--tron-bg-panel)",
              border: `1px solid ${PHASES.find((p) => p.id === expandedPhase)?.color ?? "var(--tron-border)"}40`,
            }}
          >
            <div className="flex items-center gap-2 mb-2">
              <span className="text-lg">{PHASES.find((p) => p.id === expandedPhase)?.icon}</span>
              <span
                className="font-bold uppercase text-[12px] tracking-wider"
                style={{ color: PHASES.find((p) => p.id === expandedPhase)?.color }}
              >
                {PHASES.find((p) => p.id === expandedPhase)?.label}
              </span>
              <button
                onClick={() => setExpandedPhase(null)}
                className="ml-auto text-[11px]"
                style={{ color: "var(--tron-text-dim)" }}
              >
                schließen
              </button>
            </div>
            <p style={{ color: "var(--tron-text-muted)" }}>
              {getPhaseText(expandedPhase, latestTrace, activeIndex)}
            </p>
          </div>
        )}
      </div>

      <style>{`
        @keyframes pulse-glow {
          0%, 100% { box-shadow: 0 0 10px rgba(139,92,246,0.2); }
          50% { box-shadow: 0 0 25px rgba(139,92,246,0.5); }
        }
      `}</style>
    </div>
  );
}
