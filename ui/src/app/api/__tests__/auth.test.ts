import { describe, it, expect, vi, beforeEach } from "vitest";

vi.mock("@/lib/auth/config", () => ({
  authConfig: {
    checkPassword: vi.fn(),
  },
}));
vi.mock("@/lib/auth/session", () => ({
  setSession: vi.fn(),
  clearSession: vi.fn(),
}));

describe("API auth login route", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("POST returns 400 when password missing", async () => {
    const { POST } = await import("@/app/api/auth/login/route");
    const res = await POST(
      new Request("http://x", {
        method: "POST",
        body: JSON.stringify({}),
        headers: { "Content-Type": "application/json" },
      })
    );
    expect(res.status).toBe(400);
    const json = await res.json();
    expect(json.ok).toBe(false);
    expect(json.error).toContain("password");
  });

  it("POST returns 401 when password invalid", async () => {
    const { authConfig } = await import("@/lib/auth/config");
    vi.mocked(authConfig.checkPassword).mockReturnValueOnce(false);
    const { POST } = await import("@/app/api/auth/login/route");
    const res = await POST(
      new Request("http://x", {
        method: "POST",
        body: JSON.stringify({ password: "wrong" }),
        headers: { "Content-Type": "application/json" },
      })
    );
    expect(res.status).toBe(401);
    const json = await res.json();
    expect(json.ok).toBe(false);
  });

  it("POST returns 200 when password valid", async () => {
    const { authConfig } = await import("@/lib/auth/config");
    vi.mocked(authConfig.checkPassword).mockReturnValueOnce(true);
    const { POST } = await import("@/app/api/auth/login/route");
    const res = await POST(
      new Request("http://x", {
        method: "POST",
        body: JSON.stringify({ password: "correct" }),
        headers: { "Content-Type": "application/json" },
      })
    );
    expect(res.status).toBe(200);
    const json = await res.json();
    expect(json.ok).toBe(true);
  });
});
