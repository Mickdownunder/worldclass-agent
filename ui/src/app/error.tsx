"use client";

import { useEffect } from "react";

export default function Error({
  error,
  reset,
}: {
  error: Error & { digest?: string };
  reset: () => void;
}) {
  useEffect(() => {
    console.error(error);
  }, [error]);

  return (
    <div className="flex min-h-screen flex-col items-center justify-center bg-tron-bg text-tron-text p-4">
      <h1 className="text-xl font-semibold text-tron-error">Etwas ist schiefgelaufen</h1>
      <p className="mt-2 max-w-md text-center text-sm text-tron-muted">
        {error.message}
      </p>
      <button
        type="button"
        onClick={reset}
        className="mt-8 flex h-10 items-center justify-center rounded-sm bg-transparent border-2 border-tron-accent px-6 text-sm font-bold text-tron-accent shadow-[0_0_15px_var(--tron-glow)] transition-all hover:bg-tron-accent hover:text-black hover:shadow-[0_0_25px_var(--tron-glow)] active:scale-[0.98] uppercase tracking-wider"
      >
        Erneut versuchen
      </button>
    </div>
  );
}
