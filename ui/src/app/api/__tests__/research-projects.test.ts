import { describe, it, expect, vi, beforeEach } from "vitest";

vi.mock("@/lib/auth/session", () => ({
  getSession: vi.fn(),
}));
vi.mock("@/lib/operator/research", () => ({
  listResearchProjects: vi.fn(),
}));
vi.mock("@/lib/operator/actions", () => ({
  runWorkflow: vi.fn(),
  runResearchInitAndCycleUntilDone: vi.fn(),
}));

describe("API research projects route", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("GET returns 401 when not authenticated", async () => {
    const { getSession } = await import("@/lib/auth/session");
    vi.mocked(getSession).mockResolvedValueOnce(false);
    const { GET } = await import("@/app/api/research/projects/route");
    const res = await GET();
    expect(res.status).toBe(401);
    const json = await res.json();
    expect(json.error).toBe("Unauthorized");
  });

  it("GET returns projects when authenticated", async () => {
    const { getSession } = await import("@/lib/auth/session");
    const { listResearchProjects } = await import("@/lib/operator/research");
    vi.mocked(getSession).mockResolvedValueOnce(true);
    vi.mocked(listResearchProjects).mockResolvedValueOnce([{ id: "proj-1", question: "Q?", status: "done" }]);
    const { GET } = await import("@/app/api/research/projects/route");
    const res = await GET();
    expect(res.status).toBe(200);
    const json = await res.json();
    expect(json.projects).toHaveLength(1);
    expect(json.projects[0].id).toBe("proj-1");
  });
});
