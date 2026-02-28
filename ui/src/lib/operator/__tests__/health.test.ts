import { describe, it, expect, vi, beforeEach } from "vitest";
import { execFile as _execFile } from "child_process";

function execFileError(
  _c: unknown,
  _a: unknown,
  optsOrCb: unknown,
  cb?: (err: Error | null) => void
) {
  const done = (typeof optsOrCb === "function" ? optsOrCb : cb) as (err: Error | null) => void;
  if (done) setImmediate(() => done(new Error("timeout")));
  return {} as ReturnType<typeof import("child_process").execFile>;
}

vi.mock("child_process", async (importOriginal) => {
  const actual = await importOriginal<typeof import("child_process")>();
  return { ...actual, execFile: vi.fn() };
});
vi.mock("@/lib/operator/config", () => ({ OPERATOR_ROOT: "/tmp/operator-root" }));

describe("health (data layer)", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("getHealth returns object with healthy or recent_failures", async () => {
    const { getHealth } = await import("../health");
    const result = await getHealth();
    expect(result).toBeDefined();
    expect(typeof result === "object").toBe(true);
    expect("healthy" in result || "recent_failures" in result).toBe(true);
  });

  it("getHealth returns healthy: false on exec error", async () => {
    const { execFile } = await import("child_process");
    vi.mocked(execFile).mockImplementationOnce(execFileError as never);
    const { getHealth } = await import("../health");
    const result = await getHealth();
    expect(result.healthy).toBe(false);
    expect(result.recent_failures).toBeDefined();
  });
});
