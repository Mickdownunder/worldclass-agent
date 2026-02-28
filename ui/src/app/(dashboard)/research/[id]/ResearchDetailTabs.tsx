"use client";

import { useState, useEffect } from "react";
import { VerifiedClaimSlideover } from "@/components/VerifiedClaimSlideover";
import type { TabId, Finding, Source, ReportEntry, AuditClaim, ProjectForReport } from "./types";
import { ReportTab } from "./tabs/ReportTab";
import { FindingsTab } from "./tabs/FindingsTab";
import { SourcesTab } from "./tabs/SourcesTab";
import { HistoryTab } from "./tabs/HistoryTab";
import { AuditTab } from "./tabs/AuditTab";

export function ResearchDetailTabs({
  projectId,
  initialMarkdown,
  hasPdf = false,
  project,
}: {
  projectId: string;
  initialMarkdown: string | null;
  hasPdf?: boolean;
  project?: ProjectForReport | null;
}) {
  const [activeTab, setActiveTab] = useState<TabId>("report");
  const [findings, setFindings] = useState<Finding[] | null>(null);
  const [sources, setSources] = useState<Source[] | null>(null);
  const [reports, setReports] = useState<ReportEntry[] | null>(null);
  const [auditClaims, setAuditClaims] = useState<AuditClaim[] | null>(null);
  const [loading, setLoading] = useState<Record<TabId, boolean>>({
    report: false,
    findings: false,
    sources: false,
    verlauf: false,
    audit: false,
  });
  const [slideoverTarget, setSlideoverTarget] = useState<{ open: boolean; claimId?: string }>({ open: false });

  useEffect(() => {
    /* eslint-disable react-hooks/set-state-in-effect -- lazy-load per tab */
    if (activeTab === "findings" && findings === null) {
      setLoading((l) => ({ ...l, findings: true }));
      fetch(`/api/research/projects/${projectId}/findings`)
        .then((r) => r.json())
        .then((d) => setFindings(d.findings ?? []))
        .finally(() => setLoading((l) => ({ ...l, findings: false })));
    }
    if (activeTab === "sources" && sources === null) {
      setLoading((l) => ({ ...l, sources: true }));
      fetch(`/api/research/projects/${projectId}/sources`)
        .then((r) => r.json())
        .then((d) => setSources(d.sources ?? []))
        .finally(() => setLoading((l) => ({ ...l, sources: false })));
    }
    if (activeTab === "verlauf" && reports === null) {
      setLoading((l) => ({ ...l, verlauf: true }));
      fetch(`/api/research/projects/${projectId}/reports`)
        .then((r) => r.json())
        .then((d) => setReports(d.reports ?? []))
        .finally(() => setLoading((l) => ({ ...l, verlauf: false })));
    }
    if (activeTab === "audit" && auditClaims === null) {
      setLoading((l) => ({ ...l, audit: true }));
      fetch(`/api/research/projects/${projectId}/audit`)
        .then((r) => r.json())
        .then((d) => setAuditClaims(d.claims ?? []))
        .catch(() => setAuditClaims([]))
        .finally(() => setLoading((l) => ({ ...l, audit: false })));
    }
    /* eslint-enable react-hooks/set-state-in-effect */
  }, [activeTab, projectId, findings, sources, reports, auditClaims]);

  async function sendFeedback(findingId: string, type: string) {
    try {
      await fetch("/api/research/feedback", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ project_id: projectId, type, finding_id: findingId }),
      });
    } catch { /* silent */ }
  }

  function downloadReport(filename: string, content: string) {
    const blob = new Blob([content], { type: "text/markdown" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = filename;
    a.click();
    URL.revokeObjectURL(url);
  }

  const tabs: { id: TabId; label: string }[] = [
    { id: "report", label: "Report" },
    { id: "findings", label: "Findings" },
    { id: "sources", label: "Sources" },
    { id: "verlauf", label: "History" },
    { id: "audit", label: "Audit" },
  ];

  return (
    <div className="space-y-0">
      <div
        className="flex items-end gap-px px-0 overflow-x-auto"
        style={{ borderBottom: "1px solid var(--tron-border)" }}
      >
        {tabs.map((t) => (
          <button
            key={t.id}
            type="button"
            onClick={() => setActiveTab(t.id)}
            className="relative shrink-0 px-4 py-2.5 text-[12px] font-semibold uppercase tracking-wider transition-colors"
            style={{
              color: activeTab === t.id ? "var(--tron-accent)" : "var(--tron-text-muted)",
              background: "transparent",
              borderBottom: activeTab === t.id ? "2px solid var(--tron-accent)" : "2px solid transparent",
              marginBottom: "-1px",
            }}
          >
            {t.label}
          </button>
        ))}
      </div>

      <div className="pt-4">
        {activeTab === "report" && (
          <ReportTab
            projectId={projectId}
            initialMarkdown={initialMarkdown}
            hasPdf={hasPdf}
            project={project}
            onVerifiedClick={(claimId) => setSlideoverTarget({ open: true, claimId })}
            loading={loading.report}
          />
        )}
        {activeTab === "findings" && (
          <FindingsTab
            findings={findings}
            loading={loading.findings}
            onSendFeedback={sendFeedback}
          />
        )}
        {activeTab === "sources" && <SourcesTab sources={sources} loading={loading.sources} />}
        {activeTab === "verlauf" && (
          <HistoryTab reports={reports} loading={loading.verlauf} onDownloadReport={downloadReport} />
        )}
        {activeTab === "audit" && <AuditTab auditClaims={auditClaims} loading={loading.audit} />}
      </div>

      <VerifiedClaimSlideover
        isOpen={slideoverTarget.open}
        onClose={() => setSlideoverTarget({ open: false })}
        projectId={projectId}
        targetClaimId={slideoverTarget.claimId}
      />
    </div>
  );
}
