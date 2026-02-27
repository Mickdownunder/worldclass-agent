import { describe, it, expect, vi, beforeEach } from "vitest";

vi.mock("@/lib/operator/packs", () => ({
  listPacks: vi.fn(),
}));

describe("API packs route", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("GET returns 200 with packs array", async () => {
    const { listPacks } = await import("@/lib/operator/packs");
    vi.mocked(listPacks).mockResolvedValueOnce([
      { client: "acme", date: "2025-02-27", summaryPath: "/packs/acme/2025-02-27/summary.md", packJsonPath: "/packs/acme/2025-02-27/pack.json" },
    ]);
    const { GET } = await import("@/app/api/packs/route");
    const res = await GET();
    expect(res.status).toBe(200);
    const json = await res.json();
    expect(Array.isArray(json)).toBe(true);
    expect(json).toHaveLength(1);
    expect(json[0].client).toBe("acme");
  });

  it("GET returns 500 when listPacks throws", async () => {
    const { listPacks } = await import("@/lib/operator/packs");
    vi.mocked(listPacks).mockRejectedValueOnce(new Error("readdir failed"));
    const { GET } = await import("@/app/api/packs/route");
    const res = await GET();
    expect(res.status).toBe(500);
    const json = await res.json();
    expect(json.error).toBe("readdir failed");
  });
});
