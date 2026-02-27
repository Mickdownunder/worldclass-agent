"use client";

import React, { useState, useEffect, useCallback } from "react";

interface PlumberResult {
  type: string;
  target?: string;
  file?: string;
  module?: string;
  fixed: boolean;
  diagnosis?: string;
  error?: string;
  action?: string;
  patch_path?: string | null;
  fail_count?: number;
  severity?: string;
  suggested_fix?: string;
  check?: string;
  [key: string]: unknown;
}

interface CategoryInfo {
  status: string;
  issues: PlumberResult[];
  dead_tools?: string[];
  referenced_count?: number;
  cycle_count?: number;
  reflect_count?: number;
}

interface FingerprintEntry {
  fingerprint: string;
  workflow: string;
  occurrences: number;
  snippet: string;
  non_repairable: boolean;
}

interface FingerprintStats {
  total_fingerprints: number;
  non_repairable: number;
  on_cooldown: number;
  total_occurrences: number;
  fix_attempts: number;
  fix_successes: number;
  fix_success_rate_pct: number;
  by_category: Record<string, { occurrences: number; attempts: number; successes: number }>;
  top_recurring: FingerprintEntry[];
}

interface PatchMetrics {
  total_patches: number;
  files_affected: number;
  total_loc_changed: number;
  reverts: number;
  success_rate_pct: number;
  by_category: Record<string, { count: number; loc: number; reverts: number; successes: number }>;
}

interface PlumberReport {
  timestamp: string;
  intent: string;
  governance_level: number;
  issues_found: number;
  issues_fixed: number;
  categories: Record<string, CategoryInfo>;
  summary: {
    clean: number;
    total_categories: number;
    critical: number;
    warnings: number;
  };
  results: PlumberResult[];
  fingerprints?: FingerprintStats;
  patch_metrics?: PatchMetrics;
}

interface PatchMeta {
  reason: string;
  diagnosis: string;
  file: string;
  fix?: string;
  created_at: string;
  patch_file: string;
}

const CAT_META: Record<string, { icon: string; label: string; desc: string }> = {
  shell_syntax:       { icon: "📜", label: "Shell Syntax",     desc: "bash -n Syntax-Check aller Workflow-Skripte" },
  repeated_failures:  { icon: "🔄", label: "Job Failures",     desc: "Wiederholte Fehler in Workflows" },
  python_tools:       { icon: "🐍", label: "Python Tools",     desc: "Compile + Import-Check aller Tools" },
  dependencies:       { icon: "📦", label: "Dependencies",     desc: "Installierte Packages vs. Code-Imports" },
  tool_references:    { icon: "🔗", label: "Tool References",  desc: "Workflow → Tool Verknüpfungen" },
  processes:          { icon: "⚙️", label: "Processes",         desc: "Brain-Prozesse, Zombies" },
  venv:               { icon: "🏠", label: "Venv Health",      desc: "Virtual Environment + Kern-Packages" },
};

const SEV_STYLE: Record<string, { bg: string; fg: string; label: string }> = {
  critical: { bg: "#f43f5e20", fg: "#f43f5e", label: "CRITICAL" },
  warning:  { bg: "#f59e0b20", fg: "#f59e0b", label: "WARNING" },
  info:     { bg: "#3b82f620", fg: "#3b82f6", label: "INFO" },
};

const GOV_LABELS: Record<number, { label: string; desc: string; color: string }> = {
  0: { label: "Report Only", desc: "Nur Diagnose", color: "#64748b" },
  1: { label: "Suggest",     desc: "Diagnose + Vorschlaege", color: "#3b82f6" },
  2: { label: "Dry Run",     desc: "Patches erstellen, nicht anwenden", color: "#f59e0b" },
  3: { label: "Auto Fix",    desc: "Patches anwenden", color: "#22c55e" },
};

export function PlumberTab() {
  const [report, setReport] = useState<PlumberReport | null>(null);
  const [patches, setPatches] = useState<PatchMeta[]>([]);
  const [running, setRunning] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [governance, setGovernance] = useState(2);
  const [expandedCat, setExpandedCat] = useState<string | null>(null);

  const loadPatches = useCallback(() => {
    fetch("/api/actions/plumber")
      .then((r) => r.json())
      .then((d) => { if (d.patches) setPatches(d.patches); })
      .catch(() => {});
  }, []);

  useEffect(() => { loadPatches(); }, [loadPatches]);

  const runPlumber = async () => {
    setRunning(true);
    setError(null);
    try {
      const res = await fetch("/api/actions/plumber", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ governance }),
      });
      const data = await res.json();
      if (data.ok && data.report) {
        setReport(data.report);
        loadPatches();
      } else {
        setError(data.error || "Plumber failed");
      }
    } catch (e) {
      setError(String(e));
    } finally {
      setRunning(false);
    }
  };

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between flex-wrap gap-4">
        <div className="flex items-center gap-3">
          <div
            className="w-11 h-11 rounded-xl flex items-center justify-center text-2xl"
            style={{ background: "linear-gradient(135deg, #3b82f6 0%, #8b5cf6 100%)" }}
          >
            🔧
          </div>
          <div>
            <h3 className="text-sm font-bold" style={{ color: "var(--tron-text)" }}>
              Plumber — System Doctor
            </h3>
            <p className="text-xs" style={{ color: "var(--tron-text-muted)" }}>
              7-Punkt-Diagnose: Shell, Python, Dependencies, Prozesse, Venv
            </p>
          </div>
        </div>

        <div className="flex items-center gap-3">
          <div className="flex rounded-lg overflow-hidden" style={{ border: "1px solid var(--tron-border)" }}>
            {([0, 1, 2, 3] as const).map((g) => (
              <button
                key={g}
                onClick={() => setGovernance(g)}
                className="px-3 py-1.5 text-[11px] font-semibold transition-all"
                style={{
                  background: governance === g ? GOV_LABELS[g].color : "transparent",
                  color: governance === g ? "#fff" : "var(--tron-text-muted)",
                }}
                title={GOV_LABELS[g].desc}
              >
                {GOV_LABELS[g].label}
              </button>
            ))}
          </div>

          <button
            onClick={runPlumber}
            disabled={running}
            className="px-4 py-2 rounded-lg text-xs font-bold transition-all"
            style={{
              background: running ? "var(--tron-border)" : "linear-gradient(135deg, #3b82f6, #8b5cf6)",
              color: "#fff",
              opacity: running ? 0.6 : 1,
            }}
          >
            {running ? "Scanning..." : "🩺 System-Scan starten"}
          </button>
        </div>
      </div>

      {error && (
        <div className="p-3 rounded-lg text-xs" style={{ background: "#f43f5e15", color: "#f43f5e", border: "1px solid #f43f5e40" }}>
          {error}
        </div>
      )}

      {/* Category Dashboard */}
      {report?.categories && (
        <div className="space-y-3">
          {/* Summary bar */}
          <div
            className="flex items-center gap-6 p-4 rounded-xl"
            style={{ background: "var(--tron-bg-panel)", border: "1px solid var(--tron-border)" }}
          >
            <div className="flex items-center gap-2">
              <span className="text-2xl">
                {report.summary.critical === 0 && report.summary.warnings === 0 ? "✅" : report.summary.critical > 0 ? "🚨" : "⚠️"}
              </span>
              <div>
                <div className="text-sm font-bold" style={{ color: "var(--tron-text)" }}>
                  {report.summary.clean}/{report.summary.total_categories} clean
                </div>
                <div className="text-[10px]" style={{ color: "var(--tron-text-muted)" }}>
                  {report.timestamp?.slice(0, 16).replace("T", " ")}
                </div>
              </div>
            </div>
            {report.summary.critical > 0 && (
              <span className="px-2 py-1 rounded-full text-xs font-bold" style={{ background: "#f43f5e20", color: "#f43f5e" }}>
                {report.summary.critical} critical
              </span>
            )}
            {report.summary.warnings > 0 && (
              <span className="px-2 py-1 rounded-full text-xs font-bold" style={{ background: "#f59e0b20", color: "#f59e0b" }}>
                {report.summary.warnings} warnings
              </span>
            )}
            {report.issues_fixed > 0 && (
              <span className="px-2 py-1 rounded-full text-xs font-bold" style={{ background: "#22c55e20", color: "#22c55e" }}>
                {report.issues_fixed} fixed
              </span>
            )}
            <div className="ml-auto text-xs" style={{ color: "var(--tron-text-muted)" }}>
              Gov: {GOV_LABELS[report.governance_level]?.label}
            </div>
          </div>

          {/* Fingerprint & Metrics Row */}
          {(report.fingerprints || report.patch_metrics) && (
            <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
              {/* Fingerprint Stats */}
              {report.fingerprints && report.fingerprints.total_fingerprints > 0 && (
                <div
                  className="p-4 rounded-xl space-y-3"
                  style={{ background: "var(--tron-bg-panel)", border: "1px solid var(--tron-border)" }}
                >
                  <div className="flex items-center gap-2">
                    <span className="text-lg">🧬</span>
                    <span className="text-xs font-bold" style={{ color: "var(--tron-text)" }}>
                      Error Fingerprints
                    </span>
                    <span className="ml-auto text-[10px] font-mono" style={{ color: "var(--tron-text-muted)" }}>
                      {report.fingerprints.total_fingerprints} tracked
                    </span>
                  </div>
                  <div className="grid grid-cols-3 gap-2 text-center">
                    <div className="p-2 rounded-lg" style={{ background: "var(--tron-bg)" }}>
                      <div className="text-sm font-bold" style={{ color: "var(--tron-text)" }}>
                        {report.fingerprints.fix_success_rate_pct}%
                      </div>
                      <div className="text-[9px]" style={{ color: "var(--tron-text-muted)" }}>Fix Rate</div>
                    </div>
                    <div className="p-2 rounded-lg" style={{ background: "var(--tron-bg)" }}>
                      <div className="text-sm font-bold" style={{ color: "#f43f5e" }}>
                        {report.fingerprints.non_repairable}
                      </div>
                      <div className="text-[9px]" style={{ color: "var(--tron-text-muted)" }}>Non-Repairable</div>
                    </div>
                    <div className="p-2 rounded-lg" style={{ background: "var(--tron-bg)" }}>
                      <div className="text-sm font-bold" style={{ color: "#f59e0b" }}>
                        {report.fingerprints.on_cooldown}
                      </div>
                      <div className="text-[9px]" style={{ color: "var(--tron-text-muted)" }}>On Cooldown</div>
                    </div>
                  </div>
                  {report.fingerprints.top_recurring.length > 0 && (
                    <div className="space-y-1.5">
                      <div className="text-[10px] font-bold uppercase" style={{ color: "var(--tron-text-muted)" }}>
                        Top Recurring
                      </div>
                      {report.fingerprints.top_recurring.slice(0, 3).map((e) => (
                        <div
                          key={e.fingerprint}
                          className="flex items-center gap-2 px-2 py-1.5 rounded-lg text-[10px]"
                          style={{ background: "var(--tron-bg)" }}
                        >
                          <span className="font-mono" style={{ color: "var(--tron-text-muted)" }}>
                            {e.fingerprint.slice(0, 8)}
                          </span>
                          <span className="flex-1 truncate" style={{ color: "var(--tron-text)" }}>
                            {e.workflow}: {e.snippet}
                          </span>
                          <span className="font-bold" style={{ color: e.non_repairable ? "#f43f5e" : "#f59e0b" }}>
                            {e.occurrences}x
                          </span>
                          {e.non_repairable && (
                            <span className="px-1 rounded text-[8px] font-bold" style={{ background: "#f43f5e20", color: "#f43f5e" }}>
                              NR
                            </span>
                          )}
                        </div>
                      ))}
                    </div>
                  )}
                </div>
              )}

              {/* Patch-Impact Metrics */}
              {report.patch_metrics && report.patch_metrics.total_patches > 0 && (
                <div
                  className="p-4 rounded-xl space-y-3"
                  style={{ background: "var(--tron-bg-panel)", border: "1px solid var(--tron-border)" }}
                >
                  <div className="flex items-center gap-2">
                    <span className="text-lg">📊</span>
                    <span className="text-xs font-bold" style={{ color: "var(--tron-text)" }}>
                      Patch Impact
                    </span>
                    <span className="ml-auto text-[10px] font-mono" style={{ color: "var(--tron-text-muted)" }}>
                      {report.patch_metrics.total_patches} patches
                    </span>
                  </div>
                  <div className="grid grid-cols-4 gap-2 text-center">
                    <div className="p-2 rounded-lg" style={{ background: "var(--tron-bg)" }}>
                      <div className="text-sm font-bold" style={{ color: "#22c55e" }}>
                        {report.patch_metrics.success_rate_pct}%
                      </div>
                      <div className="text-[9px]" style={{ color: "var(--tron-text-muted)" }}>Success</div>
                    </div>
                    <div className="p-2 rounded-lg" style={{ background: "var(--tron-bg)" }}>
                      <div className="text-sm font-bold" style={{ color: "var(--tron-text)" }}>
                        {report.patch_metrics.files_affected}
                      </div>
                      <div className="text-[9px]" style={{ color: "var(--tron-text-muted)" }}>Files</div>
                    </div>
                    <div className="p-2 rounded-lg" style={{ background: "var(--tron-bg)" }}>
                      <div className="text-sm font-bold" style={{ color: "var(--tron-text)" }}>
                        {report.patch_metrics.total_loc_changed}
                      </div>
                      <div className="text-[9px]" style={{ color: "var(--tron-text-muted)" }}>LOC</div>
                    </div>
                    <div className="p-2 rounded-lg" style={{ background: "var(--tron-bg)" }}>
                      <div className="text-sm font-bold" style={{ color: report.patch_metrics.reverts > 0 ? "#f43f5e" : "var(--tron-text)" }}>
                        {report.patch_metrics.reverts}
                      </div>
                      <div className="text-[9px]" style={{ color: "var(--tron-text-muted)" }}>Reverts</div>
                    </div>
                  </div>
                  {Object.keys(report.patch_metrics.by_category).length > 0 && (
                    <div className="space-y-1">
                      {Object.entries(report.patch_metrics.by_category).map(([cat, m]) => (
                        <div
                          key={cat}
                          className="flex items-center gap-2 text-[10px] px-2 py-1 rounded"
                          style={{ background: "var(--tron-bg)" }}
                        >
                          <span className="font-mono flex-1" style={{ color: "var(--tron-text)" }}>{cat}</span>
                          <span style={{ color: "var(--tron-text-muted)" }}>{m.count} patches</span>
                          <span style={{ color: "var(--tron-text-muted)" }}>{m.loc} LOC</span>
                          {m.reverts > 0 && (
                            <span style={{ color: "#f43f5e" }}>{m.reverts} rev</span>
                          )}
                        </div>
                      ))}
                    </div>
                  )}
                </div>
              )}
            </div>
          )}

          {/* Category cards */}
          {Object.entries(report.categories).map(([catId, cat]) => {
            const meta = CAT_META[catId] || { icon: "❓", label: catId, desc: "" };
            const isClean = cat.status === "clean";
            const isInfo = cat.status === "info";
            const isExpanded = expandedCat === catId;
            const hasDetails = (cat.issues?.length > 0) || (cat.dead_tools && cat.dead_tools.length > 0);

            return (
              <div key={catId}>
                <button
                  onClick={() => hasDetails ? setExpandedCat(isExpanded ? null : catId) : undefined}
                  className="w-full flex items-center gap-3 p-3 rounded-xl text-left transition-all"
                  style={{
                    background: "var(--tron-bg-panel)",
                    border: `1px solid ${isClean ? "var(--tron-border)" : isInfo ? "#3b82f640" : "#f43f5e40"}`,
                    cursor: hasDetails ? "pointer" : "default",
                  }}
                >
                  <span className="text-lg">{meta.icon}</span>
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2">
                      <span className="text-xs font-bold" style={{ color: "var(--tron-text)" }}>
                        {meta.label}
                      </span>
                      <span
                        className="px-1.5 py-0.5 rounded text-[10px] font-bold"
                        style={{
                          background: isClean ? "#22c55e20" : isInfo ? "#3b82f620" : "#f43f5e20",
                          color: isClean ? "#22c55e" : isInfo ? "#3b82f6" : "#f43f5e",
                        }}
                      >
                        {isClean ? "CLEAN" : isInfo ? "INFO" : `${cat.issues?.length || 0} ISSUES`}
                      </span>
                      {catId === "tool_references" && cat.dead_tools && cat.dead_tools.length > 0 && (
                        <span className="text-[10px]" style={{ color: "var(--tron-text-muted)" }}>
                          {cat.dead_tools.length} unreferenced
                        </span>
                      )}
                      {catId === "processes" && (
                        <span className="text-[10px]" style={{ color: "var(--tron-text-muted)" }}>
                          {cat.cycle_count} cycles, {cat.reflect_count} reflects
                        </span>
                      )}
                    </div>
                    <p className="text-[10px] mt-0.5 truncate" style={{ color: "var(--tron-text-muted)" }}>
                      {meta.desc}
                    </p>
                  </div>
                  {hasDetails && (
                    <span className="text-xs" style={{ color: "var(--tron-text-muted)" }}>
                      {isExpanded ? "▼" : "▶"}
                    </span>
                  )}
                </button>

                {/* Expanded details */}
                {isExpanded && (
                  <div className="ml-8 mt-2 space-y-2">
                    {cat.issues?.map((issue, i) => {
                      const sev = SEV_STYLE[issue.severity || "info"] || SEV_STYLE.info;
                      const target = issue.target || issue.file || issue.module || "?";
                      const msg = issue.diagnosis || issue.error || "";
                      return (
                        <div
                          key={i}
                          className="p-3 rounded-lg space-y-1"
                          style={{ background: "var(--tron-bg)", border: `1px solid ${sev.fg}30` }}
                        >
                          <div className="flex items-center gap-2">
                            <span
                              className="px-1.5 py-0.5 rounded text-[9px] font-black"
                              style={{ background: sev.bg, color: sev.fg }}
                            >
                              {sev.label}
                            </span>
                            <span className="text-xs font-mono truncate" style={{ color: "var(--tron-text)" }}>
                              {typeof target === "string" ? target.split("/").pop() : String(target)}
                            </span>
                            {issue.fail_count && (
                              <span className="text-[10px]" style={{ color: "#f43f5e" }}>
                                {issue.fail_count}x failed
                              </span>
                            )}
                          </div>
                          <p className="text-[11px] leading-relaxed" style={{ color: "var(--tron-text-muted)" }}>
                            {msg.slice(0, 300)}
                          </p>
                          {issue.suggested_fix && (
                            <div className="flex items-center gap-1.5 mt-1">
                              <span className="text-[10px]" style={{ color: "#22c55e" }}>💡</span>
                              <code className="text-[10px] font-mono" style={{ color: "#22c55e" }}>
                                {issue.suggested_fix}
                              </code>
                            </div>
                          )}
                          {issue.action && issue.action !== "none" && (
                            <div className="text-[10px] mt-1" style={{ color: "var(--tron-text-muted)" }}>
                              → {issue.action}
                            </div>
                          )}
                          {issue.patch_path && (
                            <div className="text-[10px] font-mono" style={{ color: "var(--tron-text-muted)" }}>
                              📄 {String(issue.patch_path).split("/").pop()}
                            </div>
                          )}
                        </div>
                      );
                    })}

                    {/* Dead tools list */}
                    {catId === "tool_references" && cat.dead_tools && cat.dead_tools.length > 0 && (
                      <div className="p-3 rounded-lg" style={{ background: "var(--tron-bg)", border: "1px solid var(--tron-border)" }}>
                        <div className="text-[10px] font-bold uppercase mb-2" style={{ color: "var(--tron-text-muted)" }}>
                          Unreferenced Tools ({cat.dead_tools.length})
                        </div>
                        <div className="flex flex-wrap gap-1.5">
                          {cat.dead_tools.map((tool) => (
                            <span
                              key={tool}
                              className="px-2 py-0.5 rounded text-[10px] font-mono"
                              style={{ background: "#64748b20", color: "#94a3b8" }}
                            >
                              {tool}
                            </span>
                          ))}
                        </div>
                      </div>
                    )}
                  </div>
                )}
              </div>
            );
          })}
        </div>
      )}

      {/* Patch History */}
      {patches.length > 0 && (
        <div>
          <h4 className="text-xs font-bold uppercase tracking-wider mb-3" style={{ color: "var(--tron-text-muted)" }}>
            Patch-Verlauf ({patches.length})
          </h4>
          <div className="space-y-2">
            {patches.slice(0, 10).map((p, i) => (
              <div
                key={i}
                className="flex items-center gap-3 px-3 py-2 rounded-lg text-xs"
                style={{ background: "var(--tron-bg-panel)", border: "1px solid var(--tron-border)" }}
              >
                <span>📄</span>
                <span className="font-mono flex-1" style={{ color: "var(--tron-text)" }}>
                  {(p.file || "").split("/").pop()}
                </span>
                <span style={{ color: "var(--tron-text-muted)" }}>
                  {p.fix || p.reason}
                </span>
                <span className="font-mono" style={{ color: "var(--tron-text-muted)" }}>
                  {p.created_at?.slice(0, 16).replace("T", " ")}
                </span>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Empty state */}
      {!report && patches.length === 0 && (
        <div className="text-center py-12" style={{ color: "var(--tron-text-muted)" }}>
          <div className="text-5xl mb-4">🩺</div>
          <p className="text-sm font-semibold mb-2" style={{ color: "var(--tron-text)" }}>
            System Doctor
          </p>
          <p className="text-xs max-w-md mx-auto leading-relaxed">
            Der Plumber scannt das gesamte System: Shell-Syntax, Python-Imports,
            Dependencies, Workflow-Referenzen, Prozesse und Venv-Health.
            Probleme werden erkannt und bei Gov. Level 3 automatisch repariert.
          </p>
          <button
            onClick={runPlumber}
            disabled={running}
            className="mt-4 px-5 py-2.5 rounded-lg text-xs font-bold transition-all"
            style={{
              background: "linear-gradient(135deg, #3b82f6, #8b5cf6)",
              color: "#fff",
            }}
          >
            🩺 Ersten Scan starten
          </button>
        </div>
      )}
    </div>
  );
}
