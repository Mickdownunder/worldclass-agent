"use client";

import { useCallback } from "react";
import { MarkdownView } from "@/components/MarkdownView";

export function ReportView({
  markdown,
  projectId,
}: {
  markdown: string;
  projectId: string;
}) {
  const downloadMd = useCallback(async () => {
    const res = await fetch(`/api/research/projects/${projectId}/report`);
    if (!res.ok) return;
    const data = await res.json();
    const blob = new Blob([data.markdown || ""], { type: "text/markdown" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `report-${projectId}.md`;
    a.click();
    URL.revokeObjectURL(url);
  }, [projectId]);

  return (
    <div>
      <div className="mb-3 flex justify-end">
        <button
          type="button"
          onClick={downloadMd}
          className="rounded border border-tron-accent/40 px-3 py-1 text-sm text-tron-accent hover:bg-tron-accent/10"
        >
          Download .md
        </button>
      </div>
      <div className="max-h-[70vh] overflow-auto rounded bg-tron-bg p-4">
        <MarkdownView content={markdown} className="text-sm leading-relaxed" />
      </div>
    </div>
  );
}
