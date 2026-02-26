"use client";

import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import type { Components } from "react-markdown";

interface MarkdownViewProps {
  content: string;
  className?: string;
  /**
   * When provided, [VERIFIED] tags in the text render as clickable badges
   * that trigger this callback (e.g. open the claim evidence slide-over).
   */
  onVerifiedClick?: (claimId?: string) => void;
}

/**
 * Replace [VERIFIED] in raw markdown with a sentinel inline-code marker
 * that the custom `code` component can detect and render as a badge.
 * Using a unique sentinel avoids false positives on real code blocks.
 */
const VERIFIED_SENTINEL = "§VERIFIED§";

function preprocessMarkdown(content: string, enabled: boolean): string {
  if (!enabled) return content;
  return content.replace(
    /\[VERIFIED(?::([^\]]+))?\]/g,
    (_, claimId: string | undefined) =>
      `\`${VERIFIED_SENTINEL}${claimId ? ":" + claimId : ""}\``
  );
}

function makeComponents(onVerifiedClick?: (claimId?: string) => void): Components {
  return {
    // Intercept inline code to render [VERIFIED] as a clickable badge
    code({ children, className, ...props }) {
      const text = String(children);
      if (text.startsWith(VERIFIED_SENTINEL) && onVerifiedClick) {
        const claimId = text.includes(":")
          ? text.split(":").slice(1).join(":")
          : undefined;
        return (
          <button
            type="button"
            className="verified-badge-inline"
            onClick={() => onVerifiedClick(claimId)}
            title={claimId ? `Claim: ${claimId} — click for evidence` : "Click to view evidence"}
          >
            <svg width="9" height="9" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
              <polyline points="1,4.5 3.5,7 8,1.5" />
            </svg>
            VERIFIED
          </button>
        );
      }
      // Normal inline code
      return (
        <code className={className} {...props}>
          {children}
        </code>
      );
    },
  };
}

export function MarkdownView({ content, className = "", onVerifiedClick }: MarkdownViewProps) {
  const processed = preprocessMarkdown(content, !!onVerifiedClick);
  const components = onVerifiedClick ? makeComponents(onVerifiedClick) : undefined;

  return (
    <div
      className={[
        "markdown-enterprise",
        "prose prose-invert max-w-none",
        "prose-headings:text-tron-text prose-headings:border-b prose-headings:border-tron-border prose-headings:pb-1",
        "prose-p:text-tron-text prose-p:leading-relaxed",
        "prose-a:text-tron-accent hover:prose-a:underline",
        "prose-strong:text-tron-text prose-strong:font-semibold",
        "prose-code:rounded prose-code:bg-tron-panel prose-code:px-1.5 prose-code:py-0.5 prose-code:text-tron-accent prose-code:text-[0.85em] prose-code:font-mono prose-code:border prose-code:border-tron-border",
        "prose-pre:bg-tron-panel prose-pre:border prose-pre:border-tron-border prose-pre:rounded-md",
        "prose-li:text-tron-muted prose-li:leading-relaxed",
        "prose-blockquote:border-l-tron-accent prose-blockquote:text-tron-muted prose-blockquote:not-italic",
        "prose-hr:border-tron-border",
        "prose-th:text-tron-text prose-td:text-tron-muted",
        className,
      ]
        .filter(Boolean)
        .join(" ")}
    >
      <ReactMarkdown remarkPlugins={[remarkGfm]} components={components}>
        {processed}
      </ReactMarkdown>
    </div>
  );
}
