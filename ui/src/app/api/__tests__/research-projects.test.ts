import { describe, it, expect, vi, beforeEach } from "vitest";

vi.mock("@/lib/auth/session", () => ({
  getSession: vi.fn(),
}));
vi.mock("@/lib/operator/research", () => ({
  listResearchProjects: vi.fn(),
}));
vi.mock("@/lib/operator/actions", () => ({
  submitResearchStartIntent: vi.fn(),
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
    vi.mocked(listResearchProjects).mockResolvedValueOnce([
      {
        id: "proj-1",
        question: "Q?",
        status: "done",
        phase: "done",
        created_at: "2026-03-06T00:00:00Z",
        findings_count: 0,
        reports_count: 1,
        current_spend: 0,
        domain: "general",
      },
    ]);
    const { GET } = await import("@/app/api/research/projects/route");
    const res = await GET();
    expect(res.status).toBe(200);
    const json = await res.json();
    expect(json.projects).toHaveLength(1);
    expect(json.projects[0].id).toBe("proj-1");
  });

  it("POST routes research start through control-plane intent", async () => {
    const { getSession } = await import("@/lib/auth/session");
    const { submitResearchStartIntent } = await import("@/lib/operator/actions");
    vi.mocked(getSession).mockResolvedValueOnce(true);
    vi.mocked(submitResearchStartIntent).mockResolvedValueOnce({
      ok: true,
      jobId: "job-1",
      projectId: "proj-1",
      requestEventId: "evt-1",
    });

    const request = new Request("http://localhost/api/research/projects", {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify({ question: "Question?", research_mode: "discovery", run_until_done: false }),
    });

    const { POST } = await import("@/app/api/research/projects/route");
    const res = await POST(request as never);
    const json = await res.json();

    expect(res.status).toBe(200);
    expect(vi.mocked(submitResearchStartIntent)).toHaveBeenCalledWith("Question?", "discovery", false);
    expect(json.projectId).toBe("proj-1");
  });
});
