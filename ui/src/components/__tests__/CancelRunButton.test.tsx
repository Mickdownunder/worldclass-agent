import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import { CancelRunButton } from "../CancelRunButton";

const mockRefresh = vi.fn();
vi.mock("next/navigation", () => ({
  useRouter: () => ({ refresh: mockRefresh }),
}));

describe("CancelRunButton", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("renders Cancel Run button initially", () => {
    render(<CancelRunButton projectId="proj-1" />);
    expect(screen.getByRole("button", { name: /cancel run/i })).toBeInTheDocument();
  });

  it("after clicking Cancel Run shows confirmation and Yes, cancel / No", () => {
    render(<CancelRunButton projectId="proj-1" />);
    fireEvent.click(screen.getByRole("button", { name: /cancel run/i }));
    expect(screen.getByText(/stop the running research/i)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /yes, cancel/i })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /^no$/i })).toBeInTheDocument();
  });

  it("on Yes, cancel with 200 shows Run cancelled. and calls router.refresh", async () => {
    global.fetch = vi.fn().mockResolvedValueOnce({
      ok: true,
      json: () => Promise.resolve({ killed: 1, status: "cancelled" }),
    });
    render(<CancelRunButton projectId="proj-1" />);
    fireEvent.click(screen.getByRole("button", { name: /cancel run/i }));
    fireEvent.click(screen.getByRole("button", { name: /yes, cancel/i }));
    await screen.findByText(/run cancelled\./i);
    expect(mockRefresh).toHaveBeenCalledOnce();
    expect(fetch).toHaveBeenCalledWith("/api/research/projects/proj-1/cancel", { method: "POST" });
  });

  it("on Yes, cancel with 401 shows error message", async () => {
    global.fetch = vi.fn().mockResolvedValueOnce({
      ok: false,
      json: () => Promise.resolve({ error: "Unauthorized" }),
    });
    render(<CancelRunButton projectId="proj-1" />);
    fireEvent.click(screen.getByRole("button", { name: /cancel run/i }));
    fireEvent.click(screen.getByRole("button", { name: /yes, cancel/i }));
    await screen.findByText(/unauthorized/i);
    expect(mockRefresh).not.toHaveBeenCalled();
  });

  it("sanitizes long error messages to 200 chars", async () => {
    const longError = "x".repeat(250);
    global.fetch = vi.fn().mockResolvedValueOnce({
      ok: false,
      json: () => Promise.resolve({ error: longError }),
    });
    render(<CancelRunButton projectId="proj-1" />);
    fireEvent.click(screen.getByRole("button", { name: /cancel run/i }));
    fireEvent.click(screen.getByRole("button", { name: /yes, cancel/i }));
    const expected = "x".repeat(200) + "…";
    await screen.findByText(expected);
    const msg = screen.getByText(expected);
    expect(msg.textContent).toHaveLength(201);
  });

  it("sanitizes webpack-like error to Cancel failed", async () => {
    global.fetch = vi.fn().mockResolvedValueOnce({
      ok: false,
      json: () => Promise.resolve({ error: "Something __TURBOPACK_foo bar" }),
    });
    render(<CancelRunButton projectId="proj-1" />);
    fireEvent.click(screen.getByRole("button", { name: /cancel run/i }));
    fireEvent.click(screen.getByRole("button", { name: /yes, cancel/i }));
    await screen.findByText(/cancel failed/i);
  });
});
