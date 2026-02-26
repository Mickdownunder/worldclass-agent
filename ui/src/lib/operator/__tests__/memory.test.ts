import { describe, it, expect, vi, beforeEach } from "vitest";

vi.mock("child_process", async (importOriginal) => {
  const actual = await importOriginal<typeof import("child_process")>();
  return { ...actual, execFile: vi.fn() };
});
vi.mock("@/lib/operator/config", () => ({ OPERATOR_ROOT: "/tmp/operator-root" }));

describe("memory (data layer)", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  function execFileErr(
    _c: unknown,
    _a: unknown,
    optsOrCb: unknown,
    cb?: (err: Error | null) => void
  ) {
    const done = (typeof optsOrCb === "function" ? optsOrCb : cb) as (err: Error | null) => void;
    if (done) setImmediate(() => done(new Error("ENOENT")));
    return {} as ReturnType<typeof import("child_process").execFile>;
  }

  it("getMemorySummary returns null on exec error", async () => {
    const { execFile } = await import("child_process");
    vi.mocked(execFile).mockImplementation(execFileErr as never);
    const { getMemorySummary } = await import("../memory");
    const result = await getMemorySummary();
    expect(result).toBeNull();
  });

  it("getCrossDomainInsights returns [] on exec error", async () => {
    const { execFile } = await import("child_process");
    vi.mocked(execFile).mockImplementation(execFileErr as never);
    const { getCrossDomainInsights } = await import("../memory");
    const result = await getCrossDomainInsights();
    expect(result).toEqual([]);
  });
});
