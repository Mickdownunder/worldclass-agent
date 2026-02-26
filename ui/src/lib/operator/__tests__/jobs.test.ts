import { describe, it, expect, vi, beforeEach } from "vitest";

vi.mock("fs/promises", async (importOriginal) => {
  const actual = await importOriginal<typeof import("fs/promises")>();
  return {
    ...actual,
    readdir: vi.fn(),
    readFile: vi.fn(),
    rm: vi.fn(),
  };
});
vi.mock("../config", () => ({ OPERATOR_ROOT: "/tmp/operator-root" }));

describe("jobs (data layer)", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  describe("listJobs", () => {
    it("returns empty list when jobs dir is missing", async () => {
      const { readdir } = await import("fs/promises");
      vi.mocked(readdir).mockRejectedValueOnce(new Error("ENOENT"));
      const { listJobs } = await import("../jobs");
      const result = await listJobs();
      expect(result.jobs).toEqual([]);
      expect(result.hasMore).toBe(false);
    });

    it("returns empty list when jobs dir is empty", async () => {
      const { readdir } = await import("fs/promises");
      vi.mocked(readdir).mockResolvedValueOnce([] as never);
      const { listJobs } = await import("../jobs");
      const result = await listJobs();
      expect(result.jobs).toEqual([]);
    });
  });

  describe("getJobDir", () => {
    it("returns null when job not found", async () => {
      const { readdir } = await import("fs/promises");
      vi.mocked(readdir).mockResolvedValueOnce([] as never);
      const { getJobDir } = await import("../jobs");
      const dir = await getJobDir("nonexistent");
      expect(dir).toBeNull();
    });
  });
});
