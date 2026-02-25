"use client";

import { useCallback } from "react";

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
          className="rounded border border-[#00d4ff]/40 px-3 py-1 text-sm text-[#00d4ff] hover:bg-[#00d4ff]/10"
        >
          Download .md
        </button>
      </div>
      <div className="max-h-[70vh] overflow-auto rounded bg-[#0a0a0f] p-4">
        <pre className="whitespace-pre-wrap font-sans text-sm leading-relaxed text-[#c0e0ff]">
          {markdown}
        </pre>
      </div>
    </div>
  );
}
