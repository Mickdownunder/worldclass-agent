"use client";

import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { useState } from "react";
import { ThemeToggle } from "@/components/ThemeToggle";

/* ── Icons (inline SVG, 16×16 stroke) ─────────────────────── */
function IconGrid() {
  return (
    <svg width="15" height="15" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
      <rect x="1.5" y="1.5" width="4.5" height="4.5" rx="1" />
      <rect x="9" y="1.5" width="4.5" height="4.5" rx="1" />
      <rect x="1.5" y="9" width="4.5" height="4.5" rx="1" />
      <rect x="9" y="9" width="4.5" height="4.5" rx="1" />
    </svg>
  );
}
function IconSearch() {
  return (
    <svg width="15" height="15" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round">
      <circle cx="6.5" cy="6.5" r="5" />
      <line x1="10" y1="10" x2="13.5" y2="13.5" />
    </svg>
  );
}
function IconDatabase() {
  return (
    <svg width="15" height="15" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round">
      <ellipse cx="7.5" cy="4" rx="5.5" ry="2" />
      <path d="M2 4v3.5c0 1.1 2.46 2 5.5 2s5.5-.9 5.5-2V4" />
      <path d="M2 7.5v3.5c0 1.1 2.46 2 5.5 2s5.5-.9 5.5-2V7.5" />
    </svg>
  );
}
function IconClipboard() {
  return (
    <svg width="15" height="15" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round">
      <path d="M9.5 1.5H11a1 1 0 0 1 1 1v11a1 1 0 0 1-1 1H4a1 1 0 0 1-1-1v-11a1 1 0 0 1 1-1h1.5" />
      <rect x="5.5" y="1" width="4" height="2.5" rx="1" />
      <line x1="5" y1="7" x2="10" y2="7" />
      <line x1="5" y1="9.5" x2="8.5" y2="9.5" />
    </svg>
  );
}
function IconBolt() {
  return (
    <svg width="15" height="15" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
      <path d="M9 1L3 8.5h5.5L6 14l6-7H7L9 1z" />
    </svg>
  );
}
function IconTerminal() {
  return (
    <svg width="15" height="15" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round">
      <rect x="1.5" y="2.5" width="12" height="10" rx="1.5" />
      <path d="M4 7l2 2-2 2M8.5 11h3" />
    </svg>
  );
}

/* ── Nav data ─────────────────────────────────────────────── */
const primaryNav = [
  { href: "/",         label: "Command Center",      icon: <IconGrid /> },
  { href: "/research", label: "Research Projects",   icon: <IconSearch /> },
  { href: "/research/discovery", label: "Discovery Research", icon: <IconSearch /> },
  { href: "/memory",   label: "Memory & Graph",      icon: <IconDatabase /> },
  { href: "/jobs",     label: "Audit Logs",          icon: <IconClipboard /> },
];

const secondaryNav = [
  { href: "/agents",  label: "Agents",   icon: <IconBolt /> },
  { href: "/research/insights", label: "Insights", icon: <IconTerminal /> },
];

/* ── Component ────────────────────────────────────────────── */
export function Nav() {
  const pathname = usePathname();
  const router = useRouter();
  const [mobileOpen, setMobileOpen] = useState(false);

  function isActive(href: string) {
    if (href === "/") return pathname === "/";
    return pathname === href || pathname.startsWith(href + "/");
  }

  async function logout() {
    await fetch("/api/auth/logout", { method: "POST" });
    router.push("/login");
    router.refresh();
  }

  const NavItem = ({ href, label, icon }: { href: string; label: string; icon: React.ReactNode }) => {
    const active = isActive(href);
    return (
      <Link
        href={href}
        onClick={() => setMobileOpen(false)}
        className={[
          "flex items-center gap-2.5 px-3 py-2 rounded-md text-[13px] font-medium transition-all duration-100 group relative",
          active
            ? "bg-[var(--tron-accent-dim)] text-[var(--tron-accent)]"
            : "text-[var(--tron-text-muted)] hover:text-[var(--tron-text)] hover:bg-[var(--tron-panel-hover)]",
        ].join(" ")}
      >
        {active && (
          <span className="absolute left-0 top-1/2 -translate-y-1/2 w-0.5 h-5 rounded-r bg-[var(--tron-accent)]" />
        )}
        <span className={active ? "text-[var(--tron-accent)]" : "text-[var(--tron-text-dim)] group-hover:text-[var(--tron-text-muted)]"}>
          {icon}
        </span>
        {label}
      </Link>
    );
  };

  return (
    <>
      {/* ── Desktop Sidebar ─────────────────────────────────── */}
      <aside className="hidden md:flex fixed inset-y-0 left-0 w-60 flex-col z-50"
        style={{ background: "var(--tron-bg-panel)", borderRight: "1px solid var(--tron-border)" }}>

        {/* Brand */}
        <div className="flex h-14 items-center gap-2 px-4 shrink-0"
          style={{ borderBottom: "1px solid var(--tron-border)" }}>
          <div>
            <div className="font-mono text-[11px] font-bold tracking-[0.12em] uppercase"
              style={{ color: "var(--tron-text-muted)" }}>
              Forensic AI
            </div>
            <div className="font-mono text-sm font-bold tracking-tight leading-none"
              style={{ color: "var(--tron-text)" }}>
              Operator
            </div>
          </div>
          <span className="ml-auto font-mono text-[9px] font-semibold px-1.5 py-0.5 rounded"
            style={{ background: "var(--tron-accent-dim)", color: "var(--tron-accent)", letterSpacing: "0.08em" }}>
            OS
          </span>
        </div>

        {/* Primary nav */}
        <nav className="flex-1 overflow-y-auto px-2 py-3 space-y-0.5">
          {primaryNav.map((item) => (
            <NavItem key={item.href} {...item} />
          ))}

          {/* Divider + secondary */}
          <div className="pt-4 pb-1 px-1">
            <span className="text-[10px] font-semibold uppercase tracking-[0.1em]"
              style={{ color: "var(--tron-text-dim)" }}>
              System
            </span>
          </div>
          {secondaryNav.map((item) => (
            <NavItem key={item.href} {...item} />
          ))}
        </nav>

        {/* Bottom strip */}
        <div className="shrink-0 px-3 py-3 space-y-2"
          style={{ borderTop: "1px solid var(--tron-border)" }}>
          <div className="flex items-center justify-between">
            <ThemeToggle />
            <button
              type="button"
              onClick={logout}
              className="text-[12px] font-medium transition-colors px-2 py-1 rounded"
              style={{ color: "var(--tron-text-dim)" }}
              onMouseEnter={e => (e.currentTarget.style.color = "var(--tron-error)")}
              onMouseLeave={e => (e.currentTarget.style.color = "var(--tron-text-dim)")}
            >
              Sign out
            </button>
          </div>
        </div>
      </aside>

      {/* ── Mobile top bar ──────────────────────────────────── */}
      <div className="md:hidden sticky top-0 z-50 flex h-12 items-center justify-between px-4"
        style={{ background: "var(--tron-bg-panel)", borderBottom: "1px solid var(--tron-border)" }}>
        <span className="font-mono text-sm font-bold" style={{ color: "var(--tron-text)" }}>Operator</span>
        <button
          type="button"
          onClick={() => setMobileOpen((o) => !o)}
          className="flex h-8 w-8 items-center justify-center rounded"
          style={{ color: "var(--tron-text-muted)" }}
          aria-expanded={mobileOpen}
          aria-label="Menu"
        >
          {mobileOpen ? (
            <svg width="16" height="16" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round">
              <line x1="2" y1="2" x2="14" y2="14" /><line x1="14" y1="2" x2="2" y2="14" />
            </svg>
          ) : (
            <svg width="16" height="16" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round">
              <line x1="2" y1="5" x2="14" y2="5" /><line x1="2" y1="8" x2="14" y2="8" /><line x1="2" y1="11" x2="14" y2="11" />
            </svg>
          )}
        </button>
      </div>

      {/* Mobile dropdown */}
      {mobileOpen && (
        <div className="md:hidden fixed inset-x-0 top-12 z-40 shadow-xl"
          style={{ background: "var(--tron-bg-panel)", borderBottom: "1px solid var(--tron-border)" }}>
          <nav className="px-3 py-3 space-y-0.5">
            {[...primaryNav, ...secondaryNav].map((item) => (
              <NavItem key={item.href} {...item} />
            ))}
            <div className="pt-2 flex items-center justify-between px-1">
              <ThemeToggle />
              <button type="button" onClick={logout}
                className="text-[12px] font-medium"
                style={{ color: "var(--tron-text-dim)" }}>
                Sign out
              </button>
            </div>
          </nav>
        </div>
      )}
    </>
  );
}
