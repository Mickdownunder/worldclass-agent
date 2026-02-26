"use client";

import { LoadingSpinner } from "@/components/LoadingSpinner";
import type { AuditClaim } from "../types";

interface AuditTabProps {
  auditClaims: AuditClaim[] | null;
  loading: boolean;
}

export function AuditTab({ auditClaims, loading }: AuditTabProps) {
  if (loading) return <LoadingSpinner />;
  if (!auditClaims || auditClaims.length === 0) {
    return (
      <div className="py-10 text-center">
        <p className="text-sm" style={{ color: "var(--tron-text-muted)" }}>No audit data.</p>
        <p className="mt-1 text-xs" style={{ color: "var(--tron-text-dim)" }}>
          Verify artifacts (claim_evidence_map or claim_ledger) not found for this project.
        </p>
      </div>
    );
  }
  const verifiedCount = auditClaims.filter((c) => c.verification_tier === "VERIFIED" || c.is_verified).length;
  const authoritativeCount = auditClaims.filter((c) => c.verification_tier === "AUTHORITATIVE").length;
  const unverifiedCount = auditClaims.length - verifiedCount - authoritativeCount;

  return (
    <div className="space-y-4">
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
        <div className="stat-card">
          <div className="metric-label">Verified</div>
          <div className="mt-1 text-2xl font-bold font-mono" style={{ color: "var(--tron-success)" }}>
            {verifiedCount}
          </div>
          <p className="mt-0.5 text-[10px]" style={{ color: "var(--tron-text-dim)" }}>cross-checked</p>
        </div>
        <div className="stat-card">
          <div className="metric-label">Authoritative</div>
          <div className="mt-1 text-2xl font-bold font-mono" style={{ color: "var(--tron-accent)" }}>
            {authoritativeCount}
          </div>
          <p className="mt-0.5 text-[10px]" style={{ color: "var(--tron-text-dim)" }}>primary source</p>
        </div>
        <div className="stat-card">
          <div className="metric-label">Unverified</div>
          <div className="mt-1 text-2xl font-bold font-mono" style={{ color: "var(--tron-warning)" }}>
            {unverifiedCount}
          </div>
        </div>
        <div className="stat-card">
          <div className="metric-label">Total Claims</div>
          <div className="mt-1 text-2xl font-bold font-mono" style={{ color: "var(--tron-text)" }}>
            {auditClaims.length}
          </div>
        </div>
      </div>
      <table className="data-table">
        <thead>
          <tr>
            <th style={{ width: 100 }}>Status</th>
            <th>Claim</th>
            <th style={{ width: 100 }}>Sources</th>
          </tr>
        </thead>
        <tbody>
          {auditClaims.map((c) => {
            const tier = c.verification_tier ?? (c.is_verified ? "VERIFIED" : "UNVERIFIED");
            const badgeLabel = tier === "VERIFIED" ? "Verified" : tier === "AUTHORITATIVE" ? "Authoritative" : "Unverified";
            const badgeStyle =
              tier === "VERIFIED"
                ? { background: "rgba(34,197,94,0.10)", color: "#22c55e", border: "1px solid rgba(34,197,94,0.25)" }
                : tier === "AUTHORITATIVE"
                ? { background: "rgba(59,130,246,0.10)", color: "#3b82f6", border: "1px solid rgba(59,130,246,0.25)" }
                : { background: "rgba(245,158,11,0.10)", color: "#f59e0b", border: "1px solid rgba(245,158,11,0.25)" };
            return (
            <tr key={c.claim_id}>
              <td>
                <span
                  className="inline-block rounded px-1.5 py-0.5 font-mono text-[9px] font-bold uppercase tracking-wider"
                  style={badgeStyle}
                >
                  {badgeLabel}
                </span>
              </td>
              <td>
                <p className="text-[12px] leading-relaxed" style={{ color: "var(--tron-text)" }}>{c.text}</p>
                {c.verification_reason && c.verification_tier !== "VERIFIED" && (
                  <p className="mt-0.5 text-[11px] italic" style={{ color: "var(--tron-text-dim)" }}>{c.verification_reason}</p>
                )}
              </td>
              <td>
                <span className="font-mono text-[11px]" style={{ color: "var(--tron-text-muted)" }}>{c.supporting_source_ids.length}</span>
              </td>
            </tr>
          );
          })}
        </tbody>
      </table>
    </div>
  );
}
