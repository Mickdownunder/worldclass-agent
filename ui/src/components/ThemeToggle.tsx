"use client";

import { useEffect, useState } from "react";

const STORAGE_KEY = "operator-theme";

export type Theme = "dark" | "light";

function getStoredTheme(): Theme | null {
  if (typeof window === "undefined") return null;
  const v = localStorage.getItem(STORAGE_KEY);
  if (v === "light" || v === "dark") return v;
  return null;
}

function getSystemTheme(): Theme {
  if (typeof window === "undefined") return "dark";
  return window.matchMedia("(prefers-color-scheme: light)").matches ? "light" : "dark";
}

function applyTheme(theme: Theme) {
  const html = document.documentElement;
  if (theme === "light") {
    html.setAttribute("data-theme", "light");
  } else {
    html.removeAttribute("data-theme");
  }
}

export function ThemeToggle() {
  const [theme, setThemeState] = useState<Theme | null>(null);

  useEffect(() => {
    const stored = getStoredTheme();
    const initial = stored ?? getSystemTheme();
    /* eslint-disable-next-line react-hooks/set-state-in-effect -- hydrate theme from storage */
    setThemeState(initial);
    applyTheme(initial);
  }, []);

  function toggle() {
    const next: Theme = theme === "light" ? "dark" : "light";
    setThemeState(next);
    localStorage.setItem(STORAGE_KEY, next);
    applyTheme(next);
  }

  if (theme === null) {
    return (
      <span className="inline-block h-9 w-9 rounded-sm border-2 border-tron-border bg-tron-panel" aria-hidden />
    );
  }

  const isLight = theme === "light";

  return (
    <button
      type="button"
      onClick={toggle}
      className="flex h-9 w-9 items-center justify-center rounded-sm border-2 border-tron-border bg-tron-panel text-tron-text shadow-[0_0_8px_var(--tron-glow)] transition-all hover:border-tron-accent hover:shadow-[0_0_12px_var(--tron-glow)] focus:outline-none focus:ring-2 focus:ring-tron-accent"
      title={isLight ? "Zu Dark Mode wechseln" : "Zu Light Mode wechseln"}
      aria-label={isLight ? "Zu Dark Mode wechseln" : "Zu Light Mode wechseln"}
    >
      {isLight ? (
        <span className="text-lg" aria-hidden>☀️</span>
      ) : (
        <span className="text-lg" aria-hidden>🌙</span>
      )}
    </button>
  );
}
