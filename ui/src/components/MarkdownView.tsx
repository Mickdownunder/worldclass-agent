"use client";

import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";

export function MarkdownView({
  content,
  className = "",
}: {
  content: string;
  className?: string;
}) {
  return (
    <div
      className={`markdown-tron prose prose-invert max-w-none prose-headings:text-tron-accent prose-p:text-tron-text prose-a:text-tron-accent prose-strong:text-tron-text prose-code:rounded prose-code:bg-tron-panel prose-code:px-1 prose-code:py-0.5 prose-code:text-tron-accent prose-pre:bg-tron-panel prose-pre:border prose-pre:border-tron-border prose-li:text-tron-muted ${className}`}
    >
      <ReactMarkdown remarkPlugins={[remarkGfm]}>{content}</ReactMarkdown>
    </div>
  );
}
