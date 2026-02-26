import { describe, it, expect, vi, beforeEach } from "vitest";

vi.mock("@/lib/auth/session", () => ({ getSession: vi.fn() }));
vi.mock("@/lib/operator/research", () => ({
  getResearchProject: vi.fn(),
  getFindings: vi.fn(),
}));

describe("API research findings route", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("GET returns 401 when not authenticated", async () => {
    const { getSession } = await import("@/lib/auth/session");
    vi.mocked(getSession).mockResolvedValueOnce(false);
    const { GET } = await import("@/app/api/research/projects/[id]/findings/route");
    const res = await GET({} as Request, { params: Promise.resolve({ id: "proj-1" }) });
    expect(res.status).toBe(401);
  });

  it("GET returns findings when project exists", async () => {
    const { getSession } = await import("@/lib/auth/session");
    const { getResearchProject, getFindings } = await import("@/lib/operator/research");
    vi.mocked(getSession).mockResolvedValueOnce(true);
    vi.mocked(getResearchProject).mockResolvedValueOnce({ id: "proj-1" } as never);
    vi.mocked(getFindings).mockResolvedValueOnce([{ id: "f1", title: "F1" }] as never);
    const { GET } = await import("@/app/api/research/projects/[id]/findings/route");
    const res = await GET({} as Request, { params: Promise.resolve({ id: "proj-1" }) });
    expect(res.status).toBe(200);
    const json = await res.json();
    expect(json.findings).toHaveLength(1);
    expect(json.findings[0].title).toBe("F1");
  });
});
