"use client";

import { useEffect, useState, useRef } from "react";

interface AuditClaim {
  claim_id: string;
  text: string;
  is_verified: boolean;
  verification_reason?: string;
  supporting_source_ids: string[];
}

interface Source {
  id: string;
  url?: string;
  reliability_score?: number;
  score_source?: "initial" | "verified";
}

interface VerifiedClaimSlideoverProps {
  isOpen: boolean;
  onClose: () => void;
  projectId: string;
  targetClaimId?: string;
}

export function VerifiedClaimSlideover({
  isOpen,
  onClose,
  projectId,
  targetClaimId,
}: VerifiedClaimSlideoverProps) {
  const [claims, setClaims] = useState<AuditClaim[]>([]);
  const [sources, setSources] = useState<Map<string, Source>>(new Map());
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const fetchedRef = useRef(false);
  const panelRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!isOpen) return;
    if (fetchedRef.current) return;
    fetchedRef.current = true;
    /* eslint-disable-next-line react-hooks/set-state-in-effect -- start fetch when slideover opens */
    setLoading(true);
    setError(null);

    Promise.all([
      fetch(`/api/research/projects/${projectId}/audit`).then((r) => r.json()),
      fetch(`/api/research/projects/${projectId}/sources`).then((r) => r.json()),
    ])
      .then(([auditData, sourceData]) => {
        const allClaims: AuditClaim[] = auditData.claims ?? [];
        setClaims(targetClaimId ? allClaims : allClaims.filter((c) => c.is_verified));
        const srcMap = new Map<string, Source>();
        for (const s of sourceData.sources ?? []) {
          srcMap.set(s.id, s);
        }
        setSources(srcMap);
      })
      .catch(() => setError("Failed to load claim evidence data."))
      .finally(() => setLoading(false));
  }, [isOpen, projectId, targetClaimId]);

  useEffect(() => {
    if (!isOpen) return;
    fetchedRef.current = false;
  }, [isOpen, projectId, targetClaimId]);

  useEffect(() => {
    if (!loading && targetClaimId && claims.length > 0) {
      const el = document.getElementById(`claim-${targetClaimId}`);
      if (el) {
        setTimeout(() => el.scrollIntoView({ behavior: "smooth", block: "center" }), 100);
        el.style.outline = "2px solid var(--tron-accent)";
        el.style.outlineOffset = "2px";
        setTimeout(() => {
          el.style.outline = "none";
        }, 2000);
      }
    }
  }, [loading, targetClaimId, claims]);

  // Close on backdrop click
  function handleBackdropClick(e: React.MouseEvent) {
    if (e.target === e.currentTarget) onClose();
  }

  // Close on Escape
  useEffect(() => {
    if (!isOpen) return;
    const handler = (e: KeyboardEvent) => { if (e.key === "Escape") onClose(); };
    document.addEventListener("keydown", handler);
    return () => document.removeEventListener("keydown", handler);
  }, [isOpen, onClose]);

  if (!isOpen) return null;

  return (
    <div
      className="fixed inset-0 z-50 flex justify-end"
      style={{ background: "rgba(0,0,0,0.55)" }}
      onClick={handleBackdropClick}
    >
      <div
        ref={panelRef}
        className="relative flex flex-col w-full max-w-[480px] h-full animate-slide-in-right overflow-hidden"
        style={{
          background: "var(--tron-bg-panel)",
          borderLeft: "1px solid var(--tron-border)",
        }}
      >
        {/* Header */}
        <div
          className="flex h-14 shrink-0 items-center justify-between px-5"
          style={{ borderBottom: "1px solid var(--tron-border)" }}
        >
          <div className="flex items-center gap-2">
            <span
              className="inline-flex items-center gap-1.5 rounded border border-tron-success/25 bg-tron-success/10 px-2 py-1 text-[10px] font-mono font-bold uppercase text-tron-success"
            >
              <svg width="10" height="10" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
                <polyline points="1.5,5 4,7.5 8.5,2" />
              </svg>
              Verified
            </span>
            <span className="text-sm font-semibold" style={{ color: "var(--tron-text)" }}>
              Claim Evidence Map
            </span>
          </div>
          <button
            type="button"
            onClick={onClose}
            className="flex h-7 w-7 items-center justify-center rounded text-tron-muted transition-colors hover:text-tron-text"
            aria-label="Close"
          >
            <svg width="14" height="14" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round">
              <line x1="1" y1="1" x2="13" y2="13" /><line x1="13" y1="1" x2="1" y2="13" />
            </svg>
          </button>
        </div>

        {/* Meta */}
        <div className="px-5 py-3 shrink-0 flex items-center gap-3"
          style={{ borderBottom: "1px solid var(--tron-border)", background: "var(--tron-bg)" }}>
          <span className="text-[11px] font-mono" style={{ color: "var(--tron-text-dim)" }}>
            Source: <span style={{ color: "var(--tron-text-muted)" }}>claim_evidence_map_latest.json</span>
          </span>
          {!loading && (
            <span className="ml-auto text-[11px] font-mono" style={{ color: "var(--tron-text-muted)" }}>
              {claims.length} {targetClaimId ? "claim" : "verified claim"}
              {claims.length !== 1 ? "s" : ""}
            </span>
          )}
        </div>

        {/* Content */}
        <div className="flex-1 overflow-y-auto px-5 py-4 space-y-4">
          {loading && (
            <div className="flex items-center justify-center py-12">
              <div className="flex items-center gap-2" style={{ color: "var(--tron-text-muted)" }}>
                <div className="h-4 w-4 rounded-full border-2 border-t-transparent animate-spin"
                  style={{ borderColor: "var(--tron-accent)", borderTopColor: "transparent" }} />
                <span className="text-sm">Loading evidence…</span>
              </div>
            </div>
          )}

          {error && (
            <div className="rounded p-3 text-sm"
              style={{ background: "var(--tron-bg)", border: "1px solid var(--tron-error)", color: "var(--tron-error)" }}>
              {error}
            </div>
          )}

          {!loading && !error && claims.length === 0 && (
            <div className="py-12 text-center">
              <p className="text-sm" style={{ color: "var(--tron-text-muted)" }}>
                No verified claims found for this project.
              </p>
              <p className="mt-1 text-xs" style={{ color: "var(--tron-text-dim)" }}>
                Run the Verify phase to generate claim evidence data.
              </p>
            </div>
          )}

          {!loading && claims.map((claim, idx) => {
            const sourceDetails = claim.supporting_source_ids
              .map((sid) => sources.get(sid))
              .filter(Boolean) as Source[];

            return (
              <div
                key={claim.claim_id}
                id={`claim-${claim.claim_id}`}
                className="rounded-md"
                style={{
                  border: `1px solid ${
                    targetClaimId && claim.claim_id === targetClaimId
                      ? "var(--tron-accent)"
                      : "var(--tron-border)"
                  }`,
                  boxShadow:
                    targetClaimId && claim.claim_id === targetClaimId
                      ? "0 0 0 1px var(--tron-accent) inset"
                      : undefined,
                }}
              >
                {/* Claim header */}
                <div className="flex items-start gap-2 px-3 py-2.5"
                  style={{ borderBottom: sourceDetails.length > 0 || claim.verification_reason ? "1px solid var(--tron-border)" : undefined }}>
                  <span className="shrink-0 mt-0.5 font-mono text-[10px] font-bold px-1.5 py-0.5 rounded"
                    style={{
                      background: "var(--tron-bg)",
                      color: claim.is_verified ? "var(--tron-success)" : "var(--tron-text-dim)",
                      border: `1px solid ${
                        claim.is_verified ? "var(--tron-success)" : "var(--tron-border)"
                      }`,
                    }}>
                    C{String(idx + 1).padStart(2, "0")}
                  </span>
                  <p className="text-[13px] leading-relaxed flex-1" style={{ color: "var(--tron-text)" }}>
                    {claim.text}
                  </p>
                </div>

                {/* Evidence block */}
                {(sourceDetails.length > 0 || claim.verification_reason) && (
                  <div className="px-3 py-2.5 space-y-2" style={{ background: "var(--tron-bg)" }}>
                    {claim.verification_reason && (
                      <p className="text-[11px] italic" style={{ color: "var(--tron-text-muted)" }}>
                        {claim.verification_reason}
                      </p>
                    )}

                    {sourceDetails.length > 0 && (
                      <div className="space-y-1.5">
                        <span className="text-[10px] font-mono font-semibold uppercase tracking-wider" style={{ color: "var(--tron-text-dim)" }}>
                          Sources ({sourceDetails.length})
                        </span>
                        {sourceDetails.map((src) => (
                          <div key={src.id} className="flex items-center justify-between gap-2 rounded px-2 py-1.5"
                            style={{ background: "var(--tron-bg-panel)", border: "1px solid var(--tron-border)" }}>
                            <div className="min-w-0 flex-1">
                              {src.url ? (
                                <a
                                  href={src.url}
                                  target="_blank"
                                  rel="noopener noreferrer"
                                  className="block truncate text-[11px] transition-colors hover:underline"
                                  style={{ color: "var(--tron-accent)" }}
                                >
                                  {src.url}
                                </a>
                              ) : (
                                <span className="font-mono text-[11px]" style={{ color: "var(--tron-text-muted)" }}>
                                  {src.id}
                                </span>
                              )}
                            </div>
                            {src.score_source === "verified" && src.reliability_score != null && (
                              <ReliabilityScore score={src.reliability_score} />
                            )}
                          </div>
                        ))}
                      </div>
                    )}

                    {/* Unresolved source IDs */}
                    {claim.supporting_source_ids.length > sourceDetails.length && (
                      <div className="flex flex-wrap gap-1 mt-1">
                        {claim.supporting_source_ids
                          .filter((sid) => !sources.has(sid))
                          .map((sid) => (
                            <span key={sid} className="font-mono text-[10px] px-1.5 py-0.5 rounded"
                              style={{ background: "var(--tron-bg-panel)", border: "1px solid var(--tron-border)", color: "var(--tron-text-muted)" }}>
                              {sid}
                            </span>
                          ))}
                      </div>
                    )}
                  </div>
                )}
              </div>
            );
          })}
        </div>
      </div>
    </div>
  );
}

function ReliabilityScore({ score }: { score: number }) {
  const pct = Math.round(score * 100);
  const stateClass =
    score >= 0.75
      ? "border-tron-success/25 bg-tron-success/10 text-tron-success"
      : score >= 0.5
      ? "border-tron-accent/25 bg-tron-accent/10 text-tron-accent"
      : "border-tron-error/25 bg-tron-error/10 text-tron-error";
  return (
    <span
      className={`shrink-0 rounded border px-1.5 py-0.5 font-mono text-[10px] font-bold ${stateClass}`}
      title={`Reliability score: ${pct}%`}
    >
      {pct}%
    </span>
  );
}
