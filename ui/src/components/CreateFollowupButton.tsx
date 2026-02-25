"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { LoadingSpinner } from "@/components/LoadingSpinner";

export function CreateFollowupButton({ projectId }: { projectId: string }) {
  const router = useRouter();
  const [loading, setLoading] = useState(false);
  const [message, setMessage] = useState("");
  const [log, setLog] = useState("");

  async function runFollowup() {
    setLoading(true);
    setMessage("");
    setLog("");
    try {
      const res = await fetch(`/api/research/projects/${projectId}/followup`, {
        method: "POST",
      });
      const data = await res.json();
      if (data.ok) {
        setMessage("Neue Projekte aus „Suggested Next Steps“ wurden angelegt.");
        if (data.log) setLog(data.log);
        router.refresh();
      } else {
        setMessage(data.error ?? "Fehlgeschlagen");
        if (data.log) setLog(data.log);
      }
    } catch (e) {
      setMessage(String((e as Error).message));
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="mt-4 space-y-2">
      <button
        type="button"
        onClick={runFollowup}
        disabled={loading}
        className="flex h-10 items-center justify-center rounded-sm border-2 border-tron-accent bg-transparent px-4 text-sm font-bold text-tron-accent shadow-[0_0_10px_var(--tron-glow)] transition-all hover:bg-tron-accent hover:text-black hover:shadow-[0_0_20px_var(--tron-glow)] disabled:pointer-events-none disabled:opacity-50 uppercase tracking-wider"
      >
        {loading ? <LoadingSpinner className="inline-block" /> : "Aus Next Steps neue Projekte erstellen"}
      </button>
      {message && <p className="text-sm text-tron-muted">{message}</p>}
      {log && (
        <pre className="max-h-32 overflow-auto rounded-sm border border-tron-border bg-tron-bg p-2 font-mono text-xs text-tron-dim whitespace-pre-wrap">
          {log}
        </pre>
      )}
    </div>
  );
}
