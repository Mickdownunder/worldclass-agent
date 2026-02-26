import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import { StatusBadge } from "../StatusBadge";

describe("StatusBadge", () => {
  it("renders status label", () => {
    render(<StatusBadge status="done" />);
    expect(screen.getByText("DONE")).toBeInTheDocument();
  });

  it("renders custom label when provided", () => {
    render(<StatusBadge status="running" label="Läuft" />);
    expect(screen.getByText("Läuft")).toBeInTheDocument();
  });

  it("renders unknown status as UNKNOWN", () => {
    render(<StatusBadge status="custom" />);
    expect(screen.getByText("UNKNOWN")).toBeInTheDocument();
  });

  it("maps failed_insufficient_evidence to display label", () => {
    render(<StatusBadge status="failed_insufficient_evidence" />);
    expect(screen.getByText("FAILED · INSUFF. EVIDENCE")).toBeInTheDocument();
  });
});
