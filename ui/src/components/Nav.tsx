"use client";

import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { useState } from "react";
import { ThemeToggle } from "@/components/ThemeToggle";

const links = [
  { href: "/", label: "Command Center" },
  { href: "/research", label: "Research" },
  { href: "/research/insights", label: "Insights" },
  { href: "/agents", label: "Agents" },
  { href: "/jobs", label: "Jobs" },
  { href: "/packs", label: "Packs" },
  { href: "/memory", label: "Brain & Memory" },
  { href: "/clients", label: "Clients" },
];

export function Nav() {
  const pathname = usePathname();
  const router = useRouter();
  const [mobileOpen, setMobileOpen] = useState(false);

  async function logout() {
    await fetch("/api/auth/logout", { method: "POST" });
    router.push("/login");
    router.refresh();
  }

  return (
    <nav className="sticky top-0 z-50 border-b-2 border-tron-border bg-tron-panel/90 backdrop-blur-md shadow-[0_4px_20px_var(--tron-glow)]">
      <div className="mx-auto max-w-6xl px-4 py-3 sm:px-6">
        <div className="flex min-h-[44px] items-center justify-between gap-4">
          <Link href="/" className="text-xl font-bold tracking-tight text-tron-text">
            Operator
          </Link>

          {/* Desktop: inline links */}
          <div className="hidden flex-wrap items-center gap-3 md:flex md:gap-4">
            {links.map(({ href, label }) => {
              const isActive =
                href === "/"
                  ? pathname === "/"
                  : pathname === href || pathname.startsWith(href + "/");
              return (
                <Link
                  key={href}
                  href={href}
                  className={`flex h-10 items-center justify-center rounded-sm border-2 border-transparent px-4 text-sm font-bold uppercase tracking-widest transition-all ${
                    isActive
                      ? "border-tron-accent text-tron-accent shadow-[inset_0_0_15px_var(--tron-glow)] bg-tron-accent/10"
                      : "text-tron-muted hover:border-tron-border hover:text-tron-text hover:shadow-[0_0_10px_var(--tron-glow)]"
                  }`}
                >
                  {label}
                </Link>
              );
            })}
          </div>

          <div className="flex items-center gap-3">
            <ThemeToggle />
            <button
              type="button"
              onClick={logout}
              className="flex h-10 items-center text-sm font-bold uppercase tracking-widest text-tron-dim hover:text-tron-accent md:ml-auto md:px-3 transition-all hover:text-shadow-[0_0_10px_var(--tron-glow)]"
            >
              Abmelden
            </button>
            {/* Mobile hamburger */}
            <button
              type="button"
              onClick={() => setMobileOpen((o) => !o)}
              className="flex h-10 items-center justify-center rounded-sm border-2 border-tron-border bg-transparent text-tron-muted hover:border-tron-accent hover:text-tron-accent hover:shadow-[0_0_10px_var(--tron-glow)] md:hidden px-3 uppercase font-bold tracking-widest"
              aria-expanded={mobileOpen}
              aria-label="Menü"
            >
              {mobileOpen ? (
                <span className="text-lg">✕</span>
              ) : (
                <span className="text-lg">☰</span>
              )}
            </button>
          </div>
        </div>

        {/* Mobile: collapsible links */}
        {mobileOpen && (
          <div
            className="mt-3 flex flex-col gap-1 border-t border-tron-border pt-3 md:hidden"
            role="region"
            aria-label="Navigation"
          >
            {links.map(({ href, label }) => {
              const isActive =
                href === "/"
                  ? pathname === "/"
                  : pathname === href || pathname.startsWith(href + "/");
              return (
                <Link
                  key={href}
                  href={href}
                  onClick={() => setMobileOpen(false)}
                  className={`min-h-[44px] flex items-center rounded-md border border-transparent px-3 text-sm transition ${
                    isActive
                      ? "bg-tron-text text-tron-bg font-medium shadow-sm"
                      : "text-tron-muted hover:bg-tron-accent/5 hover:text-tron-text"
                  }`}
                >
                  {label}
                </Link>
              );
            })}
          </div>
        )}
      </div>
    </nav>
  );
}
