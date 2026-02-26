import { describe, it, expect, vi, beforeEach } from "vitest";

vi.mock("@/lib/operator/health", () => ({
  getHealth: vi.fn(),
}));

describe("API health route", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("GET returns JSON from getHealth", async () => {
    const { getHealth } = await import("@/lib/operator/health");
    vi.mocked(getHealth).mockResolvedValueOnce({ healthy: true, jobs_total: 0 });
    const { GET } = await import("@/app/api/health/route");
    const res = await GET();
    expect(res.status).toBe(200);
    const json = await res.json();
    expect(json).toEqual({ healthy: true, jobs_total: 0 });
  });

  it("GET returns 500 on getHealth throw", async () => {
    const { getHealth } = await import("@/lib/operator/health");
    vi.mocked(getHealth).mockRejectedValueOnce(new Error("op not found"));
    const { GET } = await import("@/app/api/health/route");
    const res = await GET();
    expect(res.status).toBe(500);
    const json = await res.json();
    expect(json.healthy).toBe(false);
    expect(json.error).toBeDefined();
  });
});
