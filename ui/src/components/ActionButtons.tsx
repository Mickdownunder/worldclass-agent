"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";

export function RunFactoryButton() {
  const [loading, setLoading] = useState(false);
  const [message, setMessage] = useState("");
  const router = useRouter();
  async function run() {
    setLoading(true);
    setMessage("");
    try {
      const res = await fetch("/api/actions/factory", { method: "POST" });
      const data = await res.json();
      if (data.ok) {
        setMessage(data.jobId ? `Job ${data.jobId} started` : "Started");
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
        onClick={run}
        disabled={loading}
        className="flex h-10 w-full sm:w-auto items-center justify-center rounded-sm bg-transparent border-2 border-tron-accent px-5 text-sm font-bold text-tron-accent shadow-[0_0_10px_var(--tron-glow)] transition-all hover:bg-tron-accent hover:text-black hover:shadow-[0_0_20px_var(--tron-glow)] active:scale-[0.98] disabled:pointer-events-none disabled:opacity-50 uppercase tracking-wider"
      >
        {loading ? "Läuft…" : "Factory Cycle"}
      </button>
      {message && <span className="ml-2 text-sm text-tron-muted">{message}</span>}
    </div>
  );
}

export function BrainCycleButton() {
  const [loading, setLoading] = useState(false);
  const [message, setMessage] = useState("");
  const router = useRouter();
  async function run() {
    setLoading(true);
    setMessage("");
    try {
      const res = await fetch("/api/actions/brain-cycle", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ goal: "Decide the most impactful next action" }),
      });
      const data = await res.json();
      if (data.ok) {
        setMessage("Zyklus gestartet");
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
        onClick={run}
        disabled={loading}
        className="flex h-10 w-full sm:w-auto items-center justify-center rounded-sm bg-transparent border-2 border-tron-accent px-5 text-sm font-bold text-tron-accent shadow-[0_0_10px_var(--tron-glow)] transition-all hover:bg-tron-accent hover:text-black hover:shadow-[0_0_20px_var(--tron-glow)] active:scale-[0.98] disabled:pointer-events-none disabled:opacity-50 uppercase tracking-wider"
      >
        {loading ? "Läuft…" : "Brain Cycle"}
      </button>
      {message && <span className="ml-2 text-sm text-tron-muted">{message}</span>}
    </div>
  );
}
