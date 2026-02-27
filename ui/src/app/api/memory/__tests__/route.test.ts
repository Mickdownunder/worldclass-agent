import { describe, it, expect, vi, beforeEach } from "vitest";

vi.mock("@/lib/operator/memory", () => ({
  getMemorySummary: vi.fn(),
}));

describe("API memory route", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("GET returns 200 with summary when getMemorySummary returns data", async () => {
    const { getMemorySummary } = await import("@/lib/operator/memory");
    vi.mocked(getMemorySummary).mockResolvedValueOnce({
      totals: { episodes: 10, decisions: 5, reflections: 3, avg_quality: 0.8 },
      recent_episodes: [],
      recent_reflections: [],
      playbooks: [],
    });
    const { GET } = await import("@/app/api/memory/route");
    const res = await GET();
    expect(res.status).toBe(200);
    const json = await res.json();
    expect(json.totals.episodes).toBe(10);
    expect(json.totals.decisions).toBe(5);
  });

  it("GET returns 200 with default shape when getMemorySummary returns null", async () => {
    const { getMemorySummary } = await import("@/lib/operator/memory");
    vi.mocked(getMemorySummary).mockResolvedValueOnce(null);
    const { GET } = await import("@/app/api/memory/route");
    const res = await GET();
    expect(res.status).toBe(200);
    const json = await res.json();
    expect(json).toEqual({
      totals: {},
      recent_episodes: [],
      recent_reflections: [],
      playbooks: [],
    });
  });

  it("GET returns 500 when getMemorySummary throws", async () => {
    const { getMemorySummary } = await import("@/lib/operator/memory");
    vi.mocked(getMemorySummary).mockRejectedValueOnce(new Error("brain binary failed"));
    const { GET } = await import("@/app/api/memory/route");
    const res = await GET();
    expect(res.status).toBe(500);
    const json = await res.json();
    expect(json.error).toBe("brain binary failed");
  });
});
