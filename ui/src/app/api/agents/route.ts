import { NextResponse } from "next/server";
import { listAgents, listWorkflows } from "@/lib/operator/agents";

export const dynamic = "force-dynamic";

export async function GET() {
  try {
    const [agents, workflows] = await Promise.all([listAgents(), listWorkflows()]);
    return NextResponse.json({ agents, workflows });
  } catch (e) {
    return NextResponse.json(
      { error: String((e as Error).message) },
      { status: 500 }
    );
  }
}
