import { describe, it, expect, vi, beforeEach } from "vitest";

vi.mock("fs/promises", async (importOriginal) => {
  const actual = await importOriginal<typeof import("fs/promises")>();
  return { ...actual, readdir: vi.fn(), readFile: vi.fn() };
});
vi.mock("@/lib/operator/config", () => ({ OPERATOR_ROOT: "/tmp/operator-root" }));

describe("packs (data layer)", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("listPacks returns empty array when factory/packs missing", async () => {
    const { readdir } = await import("fs/promises");
    vi.mocked(readdir).mockRejectedValueOnce(new Error("ENOENT"));
    const { listPacks } = await import("../packs");
    const list = await listPacks();
    expect(list).toEqual([]);
  });

  it("getPack returns undefined content when pack files missing", async () => {
    const { readFile } = await import("fs/promises");
    vi.mocked(readFile).mockRejectedValue(new Error("ENOENT"));
    const { getPack } = await import("../packs");
    const pack = await getPack("client1", "2025-01-01");
    expect(pack).toBeDefined();
    expect(pack?.summaryMd).toBeUndefined();
    expect(pack?.packJson).toBeUndefined();
  });
});
