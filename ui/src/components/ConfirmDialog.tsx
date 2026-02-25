"use client";

import { useCallback, useEffect } from "react";

export function ConfirmDialog({
  open,
  title,
  message,
  confirmLabel = "Bestätigen",
  cancelLabel = "Abbrechen",
  variant = "danger",
  onConfirm,
  onCancel,
}: {
  open: boolean;
  title: string;
  message: string;
  confirmLabel?: string;
  cancelLabel?: string;
  variant?: "danger" | "primary";
  onConfirm: () => void;
  onCancel: () => void;
}) {
  const handleKeyDown = useCallback(
    (e: KeyboardEvent) => {
      if (!open) return;
      if (e.key === "Escape") onCancel();
      if (e.key === "Enter") onConfirm();
    },
    [open, onConfirm, onCancel]
  );

  useEffect(() => {
    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [handleKeyDown]);

  if (!open) return null;

  const confirmClass =
    variant === "danger"
      ? "bg-transparent border-2 border-tron-error text-tron-error shadow-[0_0_15px_rgba(255,0,85,0.4)] hover:bg-tron-error hover:text-black hover:shadow-[0_0_25px_rgba(255,0,85,0.8)] active:scale-[0.98] font-bold uppercase tracking-wider"
      : "bg-transparent border-2 border-tron-accent text-tron-accent shadow-[0_0_15px_var(--tron-glow)] hover:bg-tron-accent hover:text-black hover:shadow-[0_0_25px_var(--tron-glow)] active:scale-[0.98] font-bold uppercase tracking-wider";

  return (
    <div
      className="animate-fade-in fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-md p-4"
      role="dialog"
      aria-modal="true"
      aria-labelledby="confirm-dialog-title"
    >
      <div className="tron-panel w-full max-w-md p-6">
        <h2 id="confirm-dialog-title" className="text-xl font-bold tracking-widest text-tron-text uppercase">
          {title}
        </h2>
        <p className="mt-4 text-sm text-tron-muted">{message}</p>
        <div className="mt-8 flex justify-end gap-4">
          <button
            type="button"
            onClick={onCancel}
            className="flex h-11 items-center justify-center rounded-sm border-2 border-transparent px-5 text-sm font-bold text-tron-muted transition-colors hover:border-tron-border hover:text-tron-text uppercase tracking-wider"
          >
            {cancelLabel}
          </button>
          <button
            type="button"
            onClick={onConfirm}
            className={`flex h-11 items-center justify-center rounded-sm px-5 text-sm transition-all ${confirmClass}`}
          >
            {confirmLabel}
          </button>
        </div>
      </div>
    </div>
  );
}
