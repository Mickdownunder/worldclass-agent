"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { ThemeToggle } from "@/components/ThemeToggle";

export default function LoginPage() {
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);
  const router = useRouter();

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError("");
    setLoading(true);
    try {
      const res = await fetch("/api/auth/login", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ password }),
      });
      const data = await res.json();
      if (!data.ok) {
        setError(data.error ?? "Anmeldung fehlgeschlagen");
        return;
      }
      router.push("/");
      router.refresh();
    } catch (e) {
      setError(String((e as Error).message));
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="relative flex min-h-screen items-center justify-center bg-tron-bg text-tron-text">
      <div className="absolute right-4 top-4">
        <ThemeToggle />
      </div>
      <form onSubmit={handleSubmit} className="w-full max-w-sm space-y-6 tron-panel p-8" suppressHydrationWarning>
        <div className="text-center">
          <h1 className="text-2xl font-bold tracking-tight text-tron-text">
            Operator
          </h1>
          <p className="mt-2 text-sm text-tron-muted">Willkommen zurück</p>
        </div>
        <div className="space-y-4">
          <div>
            <label htmlFor="password" className="mb-1.5 block text-sm font-medium text-tron-muted">
              Passwort
            </label>
            <input
              id="password"
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              className="w-full rounded-sm border-2 border-tron-border bg-tron-bg px-4 py-2.5 text-sm text-tron-text placeholder-tron-dim focus:border-tron-accent focus:outline-none focus:shadow-[0_0_15px_var(--tron-glow)] transition-colors"
              placeholder="••••••••"
              autoComplete="current-password"
              disabled={loading}
              suppressHydrationWarning
            />
          </div>
          {error && (
            <p className="text-sm font-medium text-tron-error">{error}</p>
          )}
          <button
            type="submit"
            disabled={loading}
            className="flex h-11 w-full items-center justify-center rounded-sm bg-transparent border-2 border-tron-accent font-bold text-tron-accent shadow-[0_0_15px_var(--tron-glow)] transition-all hover:bg-tron-accent hover:text-black hover:shadow-[0_0_25px_var(--tron-glow)] active:scale-[0.98] disabled:pointer-events-none disabled:opacity-50 uppercase tracking-widest"
          >
            {loading ? "…" : "Anmelden"}
          </button>
        </div>
      </form>
    </div>
  );
}
