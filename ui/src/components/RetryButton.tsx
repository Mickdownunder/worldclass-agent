"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";

export function RetryButton({ jobId }: { jobId: string }) {
  const [loading, setLoading] = useState(false);
  const [message, setMessage] = useState("");
  const router = useRouter();
  async function retry() {
    setLoading(true);
    setMessage("");
    try {
      const res = await fetch("/api/actions/retry", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ job_id: jobId }),
      });
      const data = await res.json();
      if (data.ok) {
        setMessage("Retry started");
        router.refresh();
      } else {
        setMessage(data.error ?? "Failed");
      }
    } catch (e) {
      setMessage(String((e as Error).message));
    } finally {
      setLoading(false);
    }
  }
  return (
    <div>
      <button
        type="button"
        onClick={retry}
        disabled={loading}
        className="flex h-9 items-center justify-center rounded-sm border-2 border-tron-border bg-transparent px-4 text-sm font-bold text-tron-text shadow-[0_0_10px_var(--tron-glow)] transition-all hover:border-tron-accent hover:text-tron-accent hover:shadow-[0_0_20px_var(--tron-glow)] active:scale-[0.98] disabled:pointer-events-none disabled:opacity-50 uppercase"
      >
        {loading ? "…" : "Retry"}
      </button>
      {message && <span className="ml-2 text-sm text-tron-muted">{message}</span>}
    </div>
  );
}
