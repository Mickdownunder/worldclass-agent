import { describe, it, expect, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import { StartCycleButton } from "../StartCycleButton";

vi.mock("next/navigation", () => ({
  useRouter: () => ({ refresh: vi.fn() }),
}));

describe("StartCycleButton", () => {
  it("renders button with label", () => {
    render(<StartCycleButton projectId="proj-1" />);
    expect(screen.getByRole("button", { name: /nächste phase starten/i })).toBeInTheDocument();
  });
});
