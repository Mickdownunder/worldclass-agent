import { describe, it, expect, vi, beforeEach } from "vitest";

vi.mock("@/lib/auth/session", () => ({
  clearSession: vi.fn(() => Promise.resolve()),
}));

describe("API auth logout route", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("POST calls clearSession and returns 200 with ok true", async () => {
    const { clearSession } = await import("@/lib/auth/session");
    const { POST } = await import("@/app/api/auth/logout/route");
    const res = await POST();
    expect(clearSession).toHaveBeenCalledOnce();
    expect(res.status).toBe(200);
    const json = await res.json();
    expect(json).toEqual({ ok: true });
  });
});
