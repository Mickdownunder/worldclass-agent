import { describe, it, expect, vi, beforeEach } from "vitest";

vi.mock("fs/promises", async (importOriginal) => {
  const actual = await importOriginal<typeof import("fs/promises")>();
  return { ...actual, readFile: vi.fn() };
});
vi.mock("@/lib/operator/config", () => ({ OPERATOR_ROOT: "/tmp/operator-root" }));
vi.mock("@/lib/operator/jobs", () => ({ listJobs: vi.fn() }));

describe("API events route", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("GET returns events array", async () => {
    const { readFile } = await import("fs/promises");
    const { listJobs } = await import("@/lib/operator/jobs");
    vi.mocked(readFile).mockRejectedValueOnce(new Error("ENOENT"));
    vi.mocked(listJobs).mockResolvedValueOnce({ jobs: [], hasMore: false });
    const { GET } = await import("@/app/api/events/route");
    const res = await GET();
    expect(res.status).toBe(200);
    const json = await res.json();
    expect(Array.isArray(json.events)).toBe(true);
  });
});
