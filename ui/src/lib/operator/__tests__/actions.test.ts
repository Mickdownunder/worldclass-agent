import { describe, it, expect, vi, beforeEach } from "vitest";

vi.mock("child_process", async (importOriginal) => {
  const actual = await importOriginal<typeof import("child_process")>();
  return {
    ...actual,
    execFile: vi.fn(),
    spawn: vi.fn(() => ({ unref: vi.fn() })),
  };
});
vi.mock("fs/promises", async (importOriginal) => {
  const actual = await importOriginal<typeof import("fs/promises")>();
  return { ...actual, appendFile: vi.fn(), mkdir: vi.fn() };
});
vi.mock("@/lib/operator/config", () => ({ OPERATOR_ROOT: "/tmp/operator-root" }));

describe("actions (data layer)", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("runWorkflow returns error for disallowed workflow", async () => {
    const { runWorkflow } = await import("../actions");
    const result = await runWorkflow("disallowed-workflow-id");
    expect(result.ok).toBe(false);
    expect(result.error).toContain("not allowed");
  });

  it("runWorkflow allows research-init", async () => {
    const { ALLOWED_WORKFLOWS } = await import("../actions");
    expect(ALLOWED_WORKFLOWS.has("research-init")).toBe(true);
  });
});
