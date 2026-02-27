import { describe, it, expect, vi, beforeEach } from "vitest";

vi.mock("@/lib/auth/session", () => ({
  getSession: vi.fn(),
}));
vi.mock("@/lib/operator/actions", () => ({
  retryJob: vi.fn(),
}));

describe("API actions retry route", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("POST returns 401 when not authenticated", async () => {
    const { getSession } = await import("@/lib/auth/session");
    vi.mocked(getSession).mockResolvedValueOnce(false);
    const { POST } = await import("@/app/api/actions/retry/route");
    const res = await POST(
      new Request("http://x", {
        method: "POST",
        body: JSON.stringify({ job_id: "job-1" }),
        headers: { "Content-Type": "application/json" },
      })
    );
    expect(res.status).toBe(401);
    const json = await res.json();
    expect(json.ok).toBe(false);
    expect(json.error).toBe("Unauthorized");
  });

  it("POST returns 400 when job_id missing", async () => {
    const { getSession } = await import("@/lib/auth/session");
    vi.mocked(getSession).mockResolvedValueOnce(true);
    const { POST } = await import("@/app/api/actions/retry/route");
    const res = await POST(
      new Request("http://x", {
        method: "POST",
        body: JSON.stringify({}),
        headers: { "Content-Type": "application/json" },
      })
    );
    expect(res.status).toBe(400);
    const json = await res.json();
    expect(json.ok).toBe(false);
    expect(json.error).toBe("Missing job_id");
  });

  it("POST returns 400 when job_id empty after trim", async () => {
    const { getSession } = await import("@/lib/auth/session");
    vi.mocked(getSession).mockResolvedValueOnce(true);
    const { POST } = await import("@/app/api/actions/retry/route");
    const res = await POST(
      new Request("http://x", {
        method: "POST",
        body: JSON.stringify({ job_id: "   " }),
        headers: { "Content-Type": "application/json" },
      })
    );
    expect(res.status).toBe(400);
    const json = await res.json();
    expect(json.error).toBe("Missing job_id");
  });

  it("POST returns 200 with ok true when retryJob succeeds", async () => {
    const { getSession } = await import("@/lib/auth/session");
    const { retryJob } = await import("@/lib/operator/actions");
    vi.mocked(getSession).mockResolvedValueOnce(true);
    vi.mocked(retryJob).mockResolvedValueOnce({ ok: true });
    const { POST } = await import("@/app/api/actions/retry/route");
    const res = await POST(
      new Request("http://x", {
        method: "POST",
        body: JSON.stringify({ job_id: "job-123" }),
        headers: { "Content-Type": "application/json" },
      })
    );
    expect(res.status).toBe(200);
    const json = await res.json();
    expect(json.ok).toBe(true);
    expect(retryJob).toHaveBeenCalledWith("job-123");
  });

  it("POST returns 400 when retryJob returns ok false", async () => {
    const { getSession } = await import("@/lib/auth/session");
    const { retryJob } = await import("@/lib/operator/actions");
    vi.mocked(getSession).mockResolvedValueOnce(true);
    vi.mocked(retryJob).mockResolvedValueOnce({ ok: false, error: "Job not found" });
    const { POST } = await import("@/app/api/actions/retry/route");
    const res = await POST(
      new Request("http://x", {
        method: "POST",
        body: JSON.stringify({ job_id: "job-bad" }),
        headers: { "Content-Type": "application/json" },
      })
    );
    expect(res.status).toBe(400);
    const json = await res.json();
    expect(json.ok).toBe(false);
    expect(json.error).toBe("Job not found");
  });

  it("POST returns 500 when retryJob throws", async () => {
    const { getSession } = await import("@/lib/auth/session");
    const { retryJob } = await import("@/lib/operator/actions");
    vi.mocked(getSession).mockResolvedValueOnce(true);
    vi.mocked(retryJob).mockRejectedValueOnce(new Error("spawn failed"));
    const { POST } = await import("@/app/api/actions/retry/route");
    const res = await POST(
      new Request("http://x", {
        method: "POST",
        body: JSON.stringify({ job_id: "job-1" }),
        headers: { "Content-Type": "application/json" },
      })
    );
    expect(res.status).toBe(500);
    const json = await res.json();
    expect(json.ok).toBe(false);
    expect(json.error).toBe("spawn failed");
  });
});
