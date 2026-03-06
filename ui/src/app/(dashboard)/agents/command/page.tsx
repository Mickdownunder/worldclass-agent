import { CommandCenterClient } from "@/components/command-center/CommandCenterClient";
import { listCommandCenter } from "@/lib/operator/command-center";

export const dynamic = "force-dynamic";

export default async function CommandCenterPage() {
  const data = await listCommandCenter();
  return <CommandCenterClient initialData={data} />;
}
