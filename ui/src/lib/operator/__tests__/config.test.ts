import { describe, it, expect, vi, afterEach } from "vitest";

describe("config", () => {
  const origEnv = process.env.OPERATOR_ROOT;

  afterEach(() => {
    vi.resetModules();
    if (origEnv !== undefined) process.env.OPERATOR_ROOT = origEnv;
    else delete process.env.OPERATOR_ROOT;
  });

  it("OPERATOR_ROOT defaults to /root/operator when env unset", async () => {
    delete process.env.OPERATOR_ROOT;
    vi.resetModules();
    const { OPERATOR_ROOT } = await import("../config");
    expect(OPERATOR_ROOT).toBe("/root/operator");
  });

  it("OPERATOR_ROOT uses OPERATOR_ROOT env when set", async () => {
    process.env.OPERATOR_ROOT = "/custom/operator";
    vi.resetModules();
    const { OPERATOR_ROOT } = await import("../config");
    expect(OPERATOR_ROOT).toBe("/custom/operator");
  });
});
