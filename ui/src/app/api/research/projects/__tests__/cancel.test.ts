import { describe, it, expect, vi, beforeEach } from "vitest";

vi.mock("@/lib/auth/session", () => ({
  getSession: vi.fn(),
}));
vi.mock("@/lib/operator/research", () => ({
  getResearchProject: vi.fn(),
  cancelResearchProject: vi.fn(),
}));

describe("API research projects [id] cancel route", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("POST returns 401 when not authenticated", async () => {
    const { getSession } = await import("@/lib/auth/session");
    vi.mocked(getSession).mockResolvedValueOnce(false);
    const { POST } = await import("@/app/api/research/projects/[id]/cancel/route");
    const res = await POST(new Request("http://x", { method: "POST" }), {
      params: Promise.resolve({ id: "proj-123" }),
    });
    expect(res.status).toBe(401);
    const json = await res.json();
    expect(json.error).toBe("Unauthorized");
  });

  it("POST returns 400 when id missing", async () => {
    const { getSession } = await import("@/lib/auth/session");
    vi.mocked(getSession).mockResolvedValueOnce(true);
    const { POST } = await import("@/app/api/research/projects/[id]/cancel/route");
    const res = await POST(new Request("http://x", { method: "POST" }), {
      params: Promise.resolve({ id: "" }),
    });
    expect(res.status).toBe(400);
    const json = await res.json();
    expect(json.error).toBe("Missing id");
  });

  it("POST returns 404 when project not found", async () => {
    const { getSession } = await import("@/lib/auth/session");
    const { getResearchProject } = await import("@/lib/operator/research");
    vi.mocked(getSession).mockResolvedValueOnce(true);
    vi.mocked(getResearchProject).mockResolvedValueOnce(null);
    const { POST } = await import("@/app/api/research/projects/[id]/cancel/route");
    const res = await POST(new Request("http://x", { method: "POST" }), {
      params: Promise.resolve({ id: "proj-nonexistent" }),
    });
    expect(res.status).toBe(404);
    const json = await res.json();
    expect(json.error).toBe("Not found");
  });

  it("POST returns 200 with killed and status when project exists and cancel succeeds", async () => {
    const { getSession } = await import("@/lib/auth/session");
    const { getResearchProject, cancelResearchProject } = await import("@/lib/operator/research");
    vi.mocked(getSession).mockResolvedValueOnce(true);
    vi.mocked(getResearchProject).mockResolvedValueOnce({
      id: "proj-1",
      question: "Q?",
      status: "active",
    } as never);
    vi.mocked(cancelResearchProject).mockResolvedValueOnce({ killed: 1, status: "cancelled" });
    const { POST } = await import("@/app/api/research/projects/[id]/cancel/route");
    const res = await POST(new Request("http://x", { method: "POST" }), {
      params: Promise.resolve({ id: "proj-1" }),
    });
    expect(res.status).toBe(200);
    const json = await res.json();
    expect(json).toEqual({ killed: 1, status: "cancelled" });
    expect(cancelResearchProject).toHaveBeenCalledWith("proj-1");
  });

  it("POST returns 500 when cancelResearchProject throws", async () => {
    const { getSession } = await import("@/lib/auth/session");
    const { getResearchProject, cancelResearchProject } = await import("@/lib/operator/research");
    vi.mocked(getSession).mockResolvedValueOnce(true);
    vi.mocked(getResearchProject).mockResolvedValueOnce({ id: "proj-1" } as never);
    vi.mocked(cancelResearchProject).mockRejectedValueOnce(new Error("Process kill failed"));
    const { POST } = await import("@/app/api/research/projects/[id]/cancel/route");
    const res = await POST(new Request("http://x", { method: "POST" }), {
      params: Promise.resolve({ id: "proj-1" }),
    });
    expect(res.status).toBe(500);
    const json = await res.json();
    expect(json.error).toBe("Process kill failed");
  });
});
