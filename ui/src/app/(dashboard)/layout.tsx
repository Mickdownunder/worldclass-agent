import { redirect } from "next/navigation";
import { getSession } from "@/lib/auth/session";
import { Nav } from "@/components/Nav";

export default async function DashboardLayout({
  children,
}: { children: React.ReactNode }) {
  const ok = await getSession();
  if (!ok) redirect("/login");
  return (
    <div className="min-h-screen bg-tron-bg text-tron-text">
      <Nav />
      {/* Offset main content by sidebar width on desktop */}
      <main className="md:ml-60 min-h-screen">
        <div className="px-6 py-6 max-w-7xl">{children}</div>
      </main>
    </div>
  );
}
