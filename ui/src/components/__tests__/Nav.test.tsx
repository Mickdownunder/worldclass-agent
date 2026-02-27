import React from "react";
import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { Nav } from "../Nav";

const mockPush = vi.fn();
const mockRefresh = vi.fn();
vi.mock("next/navigation", () => ({
  usePathname: () => "/",
  useRouter: () => ({ push: mockPush, refresh: mockRefresh }),
}));
vi.mock("@/components/ThemeToggle", () => ({ ThemeToggle: () => <span data-testid="theme-toggle" /> }));

describe("Nav", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    global.fetch = vi.fn().mockResolvedValue({ ok: true });
  });

  it("renders primary nav labels", () => {
    render(<Nav />);
    expect(screen.getByRole("link", { name: /command center/i })).toBeInTheDocument();
    expect(screen.getByRole("link", { name: /research projects/i })).toBeInTheDocument();
    expect(screen.getByRole("link", { name: /memory & graph/i })).toBeInTheDocument();
  });

  it("renders Sign out button", () => {
    render(<Nav />);
    expect(screen.getByRole("button", { name: /sign out/i })).toBeInTheDocument();
  });

  it("on Sign out calls logout API and navigates to login", async () => {
    render(<Nav />);
    const signOutButtons = screen.getAllByRole("button", { name: /sign out/i });
    fireEvent.click(signOutButtons[0]);
    await waitFor(() => {
      expect(fetch).toHaveBeenCalledWith("/api/auth/logout", { method: "POST" });
    });
    await waitFor(() => {
      expect(mockPush).toHaveBeenCalledWith("/login");
      expect(mockRefresh).toHaveBeenCalled();
    });
  });
});
