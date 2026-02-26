import { describe, it, expect, vi, beforeEach } from "vitest";

vi.mock("fs/promises", async (importOriginal) => {
  const actual = await importOriginal<typeof import("fs/promises")>();
  return {
    ...actual,
    readdir: vi.fn(),
    readFile: vi.fn(),
    rm: vi.fn(),
    writeFile: vi.fn(),
  };
});
vi.mock("@/lib/operator/config", () => ({ OPERATOR_ROOT: "/tmp/operator-root" }));

describe("research (data layer)", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  describe("getResearchProject", () => {
    it("throws on invalid project ID (empty)", async () => {
      const { getResearchProject } = await import("../research");
      await expect(getResearchProject("")).rejects.toThrow("Invalid project ID");
    });

    it("throws on invalid project ID (traversal attempt)", async () => {
      const { getResearchProject } = await import("../research");
      await expect(getResearchProject("proj-../../etc/passwd")).rejects.toThrow("Invalid project ID");
    });

    it("throws on ID that does not match proj- pattern", async () => {
      const { getResearchProject } = await import("../research");
      await expect(getResearchProject("other")).rejects.toThrow("Invalid project ID");
    });
  });

  describe("listResearchProjects", () => {
    it("returns empty array when research dir is empty", async () => {
      const { listResearchProjects } = await import("../research");
      const list = await listResearchProjects();
      expect(Array.isArray(list)).toBe(true);
      expect(list).toEqual([]);
    });

    it("returns empty array when research dir does not exist (ENOENT)", async () => {
      const { readdir } = await import("fs/promises");
      const err = new Error("ENOENT") as NodeJS.ErrnoException;
      err.code = "ENOENT";
      vi.mocked(readdir).mockRejectedValueOnce(err);
      const { listResearchProjects } = await import("../research");
      const list = await listResearchProjects();
      expect(list).toEqual([]);
    });
  });
});
