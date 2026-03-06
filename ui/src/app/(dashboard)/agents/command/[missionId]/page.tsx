import Link from "next/link";
import { CommandCenterClient } from "@/components/command-center/CommandCenterClient";
import { listCommandCenter } from "@/lib/operator/command-center";

export const dynamic = "force-dynamic";

export default async function CommandMissionDetailPage({
  params,
}: {
  params: Promise<{ missionId: string }>;
}) {
  const { missionId } = await params;
  const data = await listCommandCenter();

  return (
    <div className="space-y-4">
      <Link
        href="/agents/command"
        className="inline-flex text-sm font-medium"
        style={{ color: "var(--tron-accent)" }}
      >
        ← Back to Command Center
      </Link>
      <CommandCenterClient initialData={data} initialSelectedMissionId={missionId} />
    </div>
  );
}
