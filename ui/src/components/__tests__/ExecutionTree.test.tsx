import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import { ExecutionTree } from "../ExecutionTree";

describe("ExecutionTree", () => {
  it("renders all phase labels", () => {
    render(
      <ExecutionTree currentPhase="explore" status="running" />
    );
    expect(screen.getByText("Explore")).toBeInTheDocument();
    expect(screen.getByText("Focus")).toBeInTheDocument();
    expect(screen.getByText("Connect")).toBeInTheDocument();
    expect(screen.getByText("Verify")).toBeInTheDocument();
    expect(screen.getByText("Synthesize")).toBeInTheDocument();
  });

  it("renders with done status", () => {
    render(
      <ExecutionTree currentPhase="synthesize" status="done" />
    );
    expect(screen.getByText("Synthesize")).toBeInTheDocument();
  });
});
