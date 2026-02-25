"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { ConfirmDialog } from "@/components/ConfirmDialog";
import { LoadingSpinner } from "@/components/LoadingSpinner";

type Action = "factory" | "brain" | null;

export function DashboardQuickActions() {
  const router = useRouter();
  const [confirmAction, setConfirmAction] = useState<Action>(null);
  const [loading, setLoading] = useState(false);
  const [message, setMessage] = useState("");

  async function runFactory() {
    setLoading(true);
    setMessage("");
    try {
      const res = await fetch("/api/actions/factory", { method: "POST" });
      const data = await res.json();
      if (data.ok) {
        setMessage(data.jobId ? `Job ${data.jobId} gestartet` : "Gestartet");
        setConfirmAction(null);
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

  async function runBrain() {
    setLoading(true);
    setMessage("");
    try {
      const res = await fetch("/api/actions/brain-cycle", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          goal: "Decide and execute the most impactful next action",
        }),
      });
      const data = await res.json();
      if (data.ok) {
        setMessage("Brain-Zyklus gestartet");
        setConfirmAction(null);
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

  const handleConfirm = () => {
    if (confirmAction === "factory") runFactory();
    if (confirmAction === "brain") runBrain();
  };

  const dialogConfig =
    confirmAction === "factory"
      ? { title: "Factory Cycle starten?", message: "Der Factory Cycle wird als Job gestartet. Fortfahren?" }
      : confirmAction === "brain"
        ? { title: "Brain Cycle starten?", message: "Der Brain-Zyklus wird im Hintergrund ausgeführt. Fortfahren?" }
        : null;

  return (
    <div className="flex flex-wrap items-center gap-4">
      <button
        type="button"
        onClick={() => setConfirmAction("factory")}
        disabled={loading}
        className="flex h-10 w-full sm:w-auto items-center justify-center rounded-sm bg-transparent border-2 border-tron-accent px-5 text-sm font-bold text-tron-accent shadow-[0_0_10px_var(--tron-glow)] transition-all hover:bg-tron-accent hover:text-black hover:shadow-[0_0_20px_var(--tron-glow)] active:scale-[0.98] disabled:pointer-events-none disabled:opacity-50 uppercase tracking-wider"
      >
        {loading && confirmAction === "factory" ? (
          <LoadingSpinner className="inline-block" />
        ) : (
          "Factory Cycle"
        )}
      </button>
      <button
        type="button"
        onClick={() => setConfirmAction("brain")}
        disabled={loading}
        className="flex h-10 w-full sm:w-auto items-center justify-center rounded-sm bg-transparent border-2 border-tron-accent px-5 text-sm font-bold text-tron-accent shadow-[0_0_10px_var(--tron-glow)] transition-all hover:bg-tron-accent hover:text-black hover:shadow-[0_0_20px_var(--tron-glow)] active:scale-[0.98] disabled:pointer-events-none disabled:opacity-50 uppercase tracking-wider"
      >
        {loading && confirmAction === "brain" ? (
          <LoadingSpinner className="inline-block" />
        ) : (
          "Brain Cycle"
        )}
      </button>
      {message && (
        <span className="text-sm text-tron-muted">{message}</span>
      )}

      {dialogConfig && (
        <ConfirmDialog
          open={!!confirmAction}
          title={dialogConfig.title}
          message={dialogConfig.message}
          confirmLabel="Starten"
          cancelLabel="Abbrechen"
          variant="primary"
          onConfirm={handleConfirm}
          onCancel={() => setConfirmAction(null)}
        />
      )}
    </div>
  );
}
