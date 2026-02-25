"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { LoadingSpinner } from "@/components/LoadingSpinner";

export function StartCycleButton({ projectId }: { projectId: string }) {
  const router = useRouter();
  const [loading, setLoading] = useState(false);
  const [message, setMessage] = useState("");

  async function startCycle() {
    setLoading(true);
    setMessage("");
    try {
      const res = await fetch(`/api/research/projects/${projectId}/cycle`, {
        method: "POST",
      });
      const data = await res.json();
      if (data.ok) {
        setMessage(data.message ?? "Phase gestartet");
        router.refresh();
      } else {
        setMessage(data.error ?? "Fehlgeschlagen");
      }
    } catch (e) {
      setMessage(String((e as Error).message));
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="flex items-center gap-2">
      <button
        type="button"
        onClick={startCycle}
        disabled={loading}
        className="flex h-11 w-full sm:w-auto items-center justify-center rounded-sm bg-transparent border-2 border-tron-accent px-5 text-sm font-bold text-tron-accent shadow-[0_0_15px_var(--tron-glow)] transition-all hover:bg-tron-accent hover:text-black hover:shadow-[0_0_25px_var(--tron-glow)] active:scale-[0.98] disabled:pointer-events-none disabled:opacity-50 uppercase tracking-widest"
      >
        {loading ? <LoadingSpinner className="inline-block" /> : "Nächste Phase starten"}
      </button>
      {message && <span className="text-sm text-tron-muted">{message}</span>}
    </div>
  );
}
