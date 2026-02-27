import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import { RuntimeStateBadge } from "../RuntimeStateBadge";

describe("RuntimeStateBadge", () => {
  it("renders RUNNING label", () => {
    render(<RuntimeStateBadge state="RUNNING" />);
    expect(screen.getByText("Läuft")).toBeInTheDocument();
  });

  it("renders DONE label", () => {
    render(<RuntimeStateBadge state="DONE" />);
    expect(screen.getByText("Fertig")).toBeInTheDocument();
  });

  it("renders STUCK label", () => {
    render(<RuntimeStateBadge state="STUCK" />);
    expect(screen.getByText("Hängt")).toBeInTheDocument();
  });

  it("includes step in title and body when state is RUNNING", () => {
    render(<RuntimeStateBadge state="RUNNING" step="research_verify" />);
    expect(screen.getByTitle(/research_verify/)).toBeInTheDocument();
    expect(screen.getByText(/research_verify/)).toBeInTheDocument();
  });

  it("does not render step when state is not RUNNING", () => {
    render(<RuntimeStateBadge state="DONE" step="report" />);
    expect(screen.getByText("Fertig")).toBeInTheDocument();
    expect(screen.queryByText(/report/)).not.toBeInTheDocument();
  });
});
