import { describe, it, expect, vi, beforeEach } from "vitest";

vi.mock("fs/promises", async (importOriginal) => {
  const actual = await importOriginal<typeof import("fs/promises")>();
  return { ...actual, readFile: vi.fn(), readdir: vi.fn() };
});
vi.mock("@/lib/operator/config", () => ({ OPERATOR_ROOT: "/tmp/operator-root" }));

describe("agents (data layer)", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("listAgents returns at least Captain (workflow agent)", async () => {
    const { readFile } = await import("fs/promises");
    vi.mocked(readFile).mockRejectedValueOnce(new Error("ENOENT"));
    const { listAgents } = await import("../agents");
    const list = await listAgents();
    expect(list.length).toBeGreaterThanOrEqual(1);
    const captain = list.find((a) => a.id === "captain");
    expect(captain).toBeDefined();
    expect(captain?.source).toBe("workflow");
  });

  it("listWorkflows returns array of workflow info", async () => {
    const { readdir } = await import("fs/promises");
    vi.mocked(readdir).mockResolvedValueOnce([
      { name: "research-init.sh", isDirectory: () => false },
    ] as never);
    const { listWorkflows } = await import("../agents");
    const list = await listWorkflows();
    expect(Array.isArray(list)).toBe(true);
    if (list.length > 0) {
      expect(list[0]).toHaveProperty("id");
      expect(list[0]).toHaveProperty("name");
    }
  });
});
