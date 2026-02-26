"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { LoadingSpinner } from "@/components/LoadingSpinner";
import type { ResearchProjectDetail } from "@/lib/operator/research";
import type { AuditData } from "@/lib/operator/research";

export function ReviewPanel({
  projectId,
  project,
  audit,
}: {
  projectId: string;
  project: ResearchProjectDetail;
  audit: AuditData | null;
}) {
  const router = useRouter();
  const [loading, setLoading] = useState<"approve" | "reject" | null>(null);
  const [message, setMessage] = useState("");

  async function handleApprove() {
    setLoading("approve");
    setMessage("");
    try {
      const res = await fetch(`/api/research/projects/${projectId}/approve`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ action: "approve" }),
      });
      const data = await res.json();
      if (!res.ok) {
        setMessage(data.error ?? "Approve failed");
        setLoading(null);
        return;
      }
      const cycleRes = await fetch(`/api/research/projects/${projectId}/cycle`, { method: "POST" });
      const cycleData = await cycleRes.json();
      if (cycleData.ok) {
        setMessage("Approved. Synthesize phase started.");
        router.refresh();
      } else {
        setMessage(cycleData.error ?? "Approve saved; start cycle manually.");
        router.refresh();
      }
    } catch (e) {
      setMessage(String((e as Error).message));
    } finally {
      setLoading(null);
    }
  }

  async function handleReject() {
    setLoading("reject");
    setMessage("");
    try {
      const res = await fetch(`/api/research/projects/${projectId}/approve`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ action: "reject" }),
      });
      const data = await res.json();
      if (!res.ok) {
        setMessage(data.error ?? "Reject failed");
        setLoading(null);
        return;
      }
      setMessage("Project rejected.");
      router.refresh();
    } catch (e) {
      setMessage(String((e as Error).message));
    } finally {
      setLoading(null);
    }
  }

  const gate = project.quality_gate?.evidence_gate;
  const metrics = gate?.metrics;

  return (
    <div
      className="rounded-lg overflow-hidden"
      style={{
        border: "1px solid color-mix(in srgb, var(--tron-amber, #f59e0b) 35%, transparent)",
        background: "color-mix(in srgb, var(--tron-amber, #f59e0b) 6%, var(--tron-bg-panel))",
      }}
    >
      <div
        className="flex items-center gap-2 px-5 py-3"
        style={{
          borderBottom: "1px solid color-mix(in srgb, var(--tron-amber, #f59e0b) 20%, transparent)",
        }}
      >
        <span
          className="h-2 w-2 rounded-full animate-pulse"
          style={{ background: "var(--tron-amber, #f59e0b)" }}
        />
        <span
          className="text-[11px] font-semibold uppercase tracking-wider"
          style={{ color: "var(--tron-amber, #f59e0b)" }}
        >
          Pending Review — Approve or Reject
        </span>
      </div>
      <div className="px-5 py-4 space-y-4">
        {metrics && (
          <div className="text-[11px]" style={{ color: "var(--tron-text-muted)" }}>
            <span className="font-semibold">Gate metrics: </span>
            {metrics.verified_claim_count} verified claims,{" "}
            {Math.round((metrics.claim_support_rate ?? 0) * 100)}% support rate,{" "}
            {metrics.findings_count} findings, {metrics.unique_source_count} sources.
          </div>
        )}
        {audit && audit.claims.length > 0 && (
          <div>
            <div className="text-[11px] font-semibold uppercase tracking-wider mb-2" style={{ color: "var(--tron-text-muted)" }}>
              Claims
            </div>
            <ul className="space-y-1 max-h-32 overflow-y-auto">
              {audit.claims.slice(0, 10).map((c, i) => (
                <li key={i} className="flex items-start gap-2 text-[11px]">
                  <span
                    className="shrink-0 w-2 h-2 rounded-full mt-1"
                    style={{
                      background: c.is_verified ? "var(--tron-success)" : "var(--tron-text-dim)",
                    }}
                  />
                  <span style={{ color: "var(--tron-text)" }}>
                    {(c.text || "").slice(0, 120)}
                    {(c.text?.length ?? 0) > 120 ? "…" : ""}
                  </span>
                </li>
              ))}
            </ul>
          </div>
        )}
        <div className="flex flex-wrap items-center gap-2 pt-2">
          <button
            type="button"
            onClick={handleApprove}
            disabled={!!loading}
            className="inline-flex items-center justify-center rounded border-2 px-4 py-2 text-sm font-bold transition-all disabled:pointer-events-none disabled:opacity-50"
            style={{
              borderColor: "var(--tron-success)",
              color: "var(--tron-success)",
              background: "color-mix(in srgb, var(--tron-success) 10%, transparent)",
            }}
          >
            {loading === "approve" ? <LoadingSpinner className="inline-block" /> : "Approve & Generate Report"}
          </button>
          <button
            type="button"
            onClick={handleReject}
            disabled={!!loading}
            className="inline-flex items-center justify-center rounded border-2 px-4 py-2 text-sm font-bold transition-all disabled:pointer-events-none disabled:opacity-50"
            style={{
              borderColor: "var(--tron-error)",
              color: "var(--tron-error)",
              background: "color-mix(in srgb, var(--tron-error) 10%, transparent)",
            }}
          >
            {loading === "reject" ? <LoadingSpinner className="inline-block" /> : "Reject"}
          </button>
          {message && <span className="text-sm" style={{ color: "var(--tron-text-muted)" }}>{message}</span>}
        </div>
      </div>
    </div>
  );
}
