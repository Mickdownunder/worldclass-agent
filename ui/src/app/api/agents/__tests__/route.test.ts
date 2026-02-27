import { describe, it, expect, vi, beforeEach } from "vitest";

vi.mock("@/lib/operator/agents", () => ({
  listAgents: vi.fn(),
  listWorkflows: vi.fn(),
}));

describe("API agents route", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("GET returns 200 with agents and workflows", async () => {
    const { listAgents, listWorkflows } = await import("@/lib/operator/agents");
    vi.mocked(listAgents).mockResolvedValueOnce([{ id: "a1", name: "Agent 1", source: "openclaw" }]);
    vi.mocked(listWorkflows).mockResolvedValueOnce([
      { id: "factory-cycle", name: "Factory Cycle", description: "Discover → Match → Pack → Deliver" },
      { id: "planner", name: "Planner", description: "Plant nächste Schritte (LLM)" },
    ]);
    const { GET } = await import("@/app/api/agents/route");
    const res = await GET();
    expect(res.status).toBe(200);
    const json = await res.json();
    expect(json.agents).toHaveLength(1);
    expect(json.agents[0].id).toBe("a1");
    expect(json.workflows).toHaveLength(2);
    expect(json.workflows[0].id).toBe("factory-cycle");
  });

  it("GET returns 500 when listAgents throws", async () => {
    const { listAgents } = await import("@/lib/operator/agents");
    vi.mocked(listAgents).mockRejectedValueOnce(new Error("fs error"));
    const { GET } = await import("@/app/api/agents/route");
    const res = await GET();
    expect(res.status).toBe(500);
    const json = await res.json();
    expect(json.error).toBe("fs error");
  });
});
