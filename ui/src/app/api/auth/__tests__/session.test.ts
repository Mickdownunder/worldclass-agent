import { describe, it, expect, vi, beforeEach } from "vitest";

vi.mock("@/lib/auth/session", () => ({
  getSession: vi.fn(),
}));

describe("API auth session route", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("GET returns ok false when not authenticated", async () => {
    const { getSession } = await import("@/lib/auth/session");
    vi.mocked(getSession).mockResolvedValueOnce(false);
    const { GET } = await import("@/app/api/auth/session/route");
    const res = await GET();
    expect(res.status).toBe(200);
    const json = await res.json();
    expect(json).toEqual({ ok: false });
  });

  it("GET returns ok true when authenticated", async () => {
    const { getSession } = await import("@/lib/auth/session");
    vi.mocked(getSession).mockResolvedValueOnce(true);
    const { GET } = await import("@/app/api/auth/session/route");
    const res = await GET();
    expect(res.status).toBe(200);
    const json = await res.json();
    expect(json).toEqual({ ok: true });
  });
});
