import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import { RetryButton } from "../RetryButton";

const mockRefresh = vi.fn();
vi.mock("next/navigation", () => ({
  useRouter: () => ({ refresh: mockRefresh }),
}));

describe("RetryButton", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("renders Retry button", () => {
    render(<RetryButton jobId="job-1" />);
    expect(screen.getByRole("button", { name: /retry/i })).toBeInTheDocument();
  });

  it("on click with 200 ok shows Retry started and calls router.refresh", async () => {
    global.fetch = vi.fn().mockResolvedValueOnce({
      ok: true,
      json: () => Promise.resolve({ ok: true }),
    });
    render(<RetryButton jobId="job-1" />);
    fireEvent.click(screen.getByRole("button", { name: /retry/i }));
    await screen.findByText(/retry started/i);
    expect(mockRefresh).toHaveBeenCalledOnce();
    expect(fetch).toHaveBeenCalledWith("/api/actions/retry", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ job_id: "job-1" }),
    });
  });

  it("on click with ok false shows error message", async () => {
    global.fetch = vi.fn().mockResolvedValueOnce({
      ok: false,
      json: () => Promise.resolve({ error: "Job not found" }),
    });
    render(<RetryButton jobId="job-1" />);
    fireEvent.click(screen.getByRole("button", { name: /retry/i }));
    await screen.findByText(/job not found/i);
    expect(mockRefresh).not.toHaveBeenCalled();
  });
});
