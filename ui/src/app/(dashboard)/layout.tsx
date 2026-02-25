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
      <main className="p-6">{children}</main>
    </div>
  );
}
