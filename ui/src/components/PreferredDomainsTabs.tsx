"use client";

import { useState } from "react";

const TIER_TABS: ReadonlyArray<{ key: string; label: "Tier 1" | "Tier 2" | "Tier 3" }> = [
  { key: "tier_1_primary", label: "Tier 1" },
  { key: "tier_2_peer_reviewed", label: "Tier 2" },
  { key: "tier_3_context_only", label: "Tier 3" },
];

type DomainRankOverrides = Record<string, string | number | string[] | undefined>;

export function PreferredDomainsTabs({ domainOverrides }: { domainOverrides: DomainRankOverrides }) {
  const [domainTab, setDomainTab] = useState<"Tier 1" | "Tier 2" | "Tier 3">("Tier 1");
  const activeTierKey = TIER_TABS.find((t) => t.label === domainTab)?.key ?? "tier_1_primary";
  const rank = domainOverrides[activeTierKey];

  const formatted =
    rank == null || rank === ""
      ? ""
      : Array.isArray(rank)
        ? rank.join(", ")
        : typeof rank === "string" && rank.length > 1
          ? rank.replace(/(\.(?:com|org|gov|eu|de|net))(?=[A-Za-z])/gi, "$1, ")
          : String(rank);
  const domains = formatted ? formatted.split(/\s*,\s*/).filter(Boolean) : [];

  const hasAny = TIER_TABS.some((t) => {
    const r = domainOverrides[t.key];
    return r != null && r !== "" && (Array.isArray(r) ? r.length > 0 : String(r).trim() !== "");
  });

  if (!hasAny) {
    return (
      <div className="text-[11px]" style={{ color: "var(--tron-text-dim)" }}>
        No overrides
      </div>
    );
  }

  return (
    <div>
      <div
        className="flex gap-0.5 mb-2"
        role="tablist"
        aria-label="Preferred domains by tier"
      >
        {TIER_TABS.map(({ label }) => (
          <button
            key={label}
            type="button"
            role="tab"
            aria-selected={domainTab === label}
            onClick={() => setDomainTab(label)}
            className="px-2.5 py-1 text-[11px] font-medium rounded transition-colors"
            style={
              domainTab === label
                ? {
                    border: "1px solid var(--tron-border)",
                    background: "var(--tron-bg)",
                    color: "var(--tron-text)",
                  }
                : {
                    border: "1px solid transparent",
                    background: "transparent",
                    color: "var(--tron-text-muted)",
                  }
            }
          >
            {label}
          </button>
        ))}
      </div>
      <div className="text-[11px] font-mono" style={{ color: "var(--tron-text)" }}>
        {domains.length === 0 ? (
          <div style={{ color: "var(--tron-text-dim)" }}>No domains</div>
        ) : domains.length > 1 ? (
          <ul className="mt-0.5 list-inside list-disc space-y-0.5">
            {domains.map((d, i) => (
              <li key={i}>{d.trim()}</li>
            ))}
          </ul>
        ) : (
          <div className="mt-0.5">{formatted}</div>
        )}
      </div>
    </div>
  );
}
