/** Shared types for research detail tabs and tab components. */

export type TabId = "report" | "findings" | "sources" | "verlauf" | "audit";

export interface Finding {
  id: string;
  url?: string;
  title?: string;
  excerpt?: string;
  source?: string;
  confidence?: number;
}

export interface Source {
  id: string;
  url?: string;
  type?: string;
  confidence?: number;
  reliability_score?: number;
  score_source?: "initial" | "verified";
}

export interface ReportEntry {
  filename: string;
  content: string;
}

export type VerificationTier = "VERIFIED" | "AUTHORITATIVE" | "UNVERIFIED";

export interface AuditClaim {
  claim_id: string;
  text: string;
  is_verified: boolean;
  verification_tier?: VerificationTier;
  verification_reason?: string;
  supporting_source_ids: string[];
}

export interface ProjectForReport {
  last_phase_at?: string;
  current_spend?: number;
  quality_gate?: {
    critic_score?: number;
    evidence_gate?: {
      metrics?: {
        verified_claim_count?: number;
        claim_support_rate?: number;
        unique_source_count?: number;
        findings_count?: number;
      };
    };
  };
}

export const FEEDBACK_TYPES = [
  { type: "excellent", label: "Excellent" },
  { type: "ignore", label: "Irrelevant" },
  { type: "wrong", label: "Incorrect" },
  { type: "dig_deeper", label: "Dig Deeper" },
] as const;
