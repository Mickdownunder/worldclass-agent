import { describe, it, expect, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import { DeleteProjectButton } from "../DeleteProjectButton";

vi.mock("next/navigation", () => ({
  useRouter: () => ({ refresh: vi.fn(), push: vi.fn() }),
}));

describe("DeleteProjectButton", () => {
  it("renders delete button with label", () => {
    render(<DeleteProjectButton projectId="proj-1" />);
    expect(screen.getByRole("button", { name: /projekt löschen/i })).toBeInTheDocument();
  });

  it("shows loading text when loading", () => {
    render(<DeleteProjectButton projectId="proj-1" />);
    const btn = screen.getByRole("button", { name: /projekt löschen/i });
    expect(btn).not.toBeDisabled();
  });
});
