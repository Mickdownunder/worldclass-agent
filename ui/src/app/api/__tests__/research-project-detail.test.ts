import { describe, it, expect, vi, beforeEach } from "vitest";

vi.mock("@/lib/auth/session", () => ({ getSession: vi.fn() }));
vi.mock("@/lib/operator/research", () => ({
  getResearchProject: vi.fn(),
  deleteResearchProject: vi.fn(),
}));

describe("API research project detail route", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("GET returns 401 when not authenticated", async () => {
    const { getSession } = await import("@/lib/auth/session");
    vi.mocked(getSession).mockResolvedValueOnce(false);
    const { GET } = await import("@/app/api/research/projects/[id]/route");
    const res = await GET({} as Request, { params: Promise.resolve({ id: "proj-1" }) });
    expect(res.status).toBe(401);
    const json = await res.json();
    expect(json.error).toBe("Unauthorized");
  });

  it("GET returns 404 when project not found", async () => {
    const { getSession } = await import("@/lib/auth/session");
    const { getResearchProject } = await import("@/lib/operator/research");
    vi.mocked(getSession).mockResolvedValueOnce(true);
    vi.mocked(getResearchProject).mockResolvedValueOnce(null);
    const { GET } = await import("@/app/api/research/projects/[id]/route");
    const res = await GET({} as Request, { params: Promise.resolve({ id: "proj-missing" }) });
    expect(res.status).toBe(404);
    const json = await res.json();
    expect(json.error).toBe("Not found");
  });

  it("GET returns project when found", async () => {
    const { getSession } = await import("@/lib/auth/session");
    const { getResearchProject } = await import("@/lib/operator/research");
    vi.mocked(getSession).mockResolvedValueOnce(true);
    vi.mocked(getResearchProject).mockResolvedValueOnce({
      id: "proj-1",
      question: "Q?",
      status: "done",
      phase: "done",
    } as never);
    const { GET } = await import("@/app/api/research/projects/[id]/route");
    const res = await GET({} as Request, { params: Promise.resolve({ id: "proj-1" }) });
    expect(res.status).toBe(200);
    const json = await res.json();
    expect(json.id).toBe("proj-1");
  });
});
