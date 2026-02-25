"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";

const links = [
  { href: "/", label: "Command Center" },
  { href: "/research", label: "Research" },
  { href: "/agents", label: "Agents" },
  { href: "/jobs", label: "Jobs" },
  { href: "/packs", label: "Packs" },
  { href: "/memory", label: "Brain & Memory" },
  { href: "/clients", label: "Clients" },
];

export function Nav() {
  const router = useRouter();
  async function logout() {
    await fetch("/api/auth/logout", { method: "POST" });
    router.push("/login");
    router.refresh();
  }
  return (
    <nav className="border-b border-[#00d4ff]/20 bg-[#0d1117]/95">
      <div className="mx-auto flex max-w-6xl flex-wrap items-center gap-4 px-4 py-3 sm:gap-6 sm:px-6">
        <Link href="/" className="text-lg font-semibold text-[#00d4ff]">
          Operator
        </Link>
        <div className="flex flex-wrap gap-3 sm:gap-4">
          {links.map(({ href, label }) => (
            <Link
              key={href}
              href={href}
              className="text-sm text-[#88aacc] transition hover:text-[#00d4ff]"
            >
              {label}
            </Link>
          ))}
        </div>
        <button
          type="button"
          onClick={logout}
          className="ml-auto text-sm text-[#6688aa] hover:text-[#00d4ff]"
        >
          Logout
        </button>
      </div>
    </nav>
  );
}
