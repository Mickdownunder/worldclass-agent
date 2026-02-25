"use client";

export function LoadingSpinner({ className = "" }: { className?: string }) {
  return (
    <div
      className={`inline-block h-6 w-6 animate-spin rounded-full border-2 border-tron-accent/30 border-t-tron-accent ${className}`}
      role="status"
      aria-label="Lädt"
    />
  );
}
