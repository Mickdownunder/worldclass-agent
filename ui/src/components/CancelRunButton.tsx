"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { LoadingSpinner } from "@/components/LoadingSpinner";

export function CancelRunButton({ projectId }: { projectId: string }) {
  const router = useRouter();
  const [loading, setLoading] = useState(false);
  const [confirm, setConfirm] = useState(false);
  const [message, setMessage] = useState("");

  async function cancel() {
    setLoading(true);
    setMessage("");
    try {
      const res = await fetch(`/api/research/projects/${projectId}/cancel`, { method: "POST" });
      const data = await res.json();
      if (!res.ok) {
        setMessage(data.error ?? "Cancel failed");
        setLoading(false);
        return;
      }
      setMessage("Run cancelled.");
      setConfirm(false);
      router.refresh();
    } catch (e) {
      setMessage(String((e as Error).message));
    } finally {
      setLoading(false);
    }
  }

  if (!confirm) {
    return (
      <div className="flex items-center gap-2">
        <button
          type="button"
          onClick={() => setConfirm(true)}
          className="flex h-11 items-center justify-center rounded-sm border-2 px-5 text-sm font-bold transition-all hover:opacity-90"
          style={{
            borderColor: "var(--tron-error)",
            color: "var(--tron-error)",
            background: "transparent",
          }}
        >
          Cancel Run
        </button>
        {message && <span className="text-sm" style={{ color: "var(--tron-text-muted)" }}>{message}</span>}
      </div>
    );
  }

  return (
    <div className="flex items-center gap-2">
      <span className="text-[11px]" style={{ color: "var(--tron-text-muted)" }}>
        Stop the running research?
      </span>
      <button
        type="button"
        onClick={cancel}
        disabled={loading}
        className="flex h-11 items-center justify-center rounded-sm border-2 px-5 text-sm font-bold transition-all disabled:pointer-events-none disabled:opacity-50"
        style={{
          borderColor: "var(--tron-error)",
          color: "var(--tron-error)",
          background: "color-mix(in srgb, var(--tron-error) 12%, transparent)",
        }}
      >
        {loading ? <LoadingSpinner className="inline-block" /> : "Yes, cancel"}
      </button>
      <button
        type="button"
        onClick={() => setConfirm(false)}
        disabled={loading}
        className="flex h-11 items-center justify-center rounded-sm border px-5 text-sm font-bold transition-all disabled:pointer-events-none"
        style={{ borderColor: "var(--tron-border)", color: "var(--tron-text)" }}
      >
        No
      </button>
      {message && <span className="text-sm" style={{ color: "var(--tron-text-muted)" }}>{message}</span>}
    </div>
  );
}
