import { describe, it, expect } from "vitest";
import type { RuntimeState } from "../progress";
import { RUNTIME_STATE_LABELS, RUNTIME_STATE_HINT } from "../progress";

const RUNTIME_STATES: RuntimeState[] = [
  "RUNNING",
  "IDLE",
  "STUCK",
  "ERROR_LOOP",
  "FAILED",
  "DONE",
];

describe("progress", () => {
  it("RUNTIME_STATE_LABELS has an entry for every RuntimeState", () => {
    expect(Object.keys(RUNTIME_STATE_LABELS).sort()).toEqual([...RUNTIME_STATES].sort());
    for (const state of RUNTIME_STATES) {
      expect(typeof RUNTIME_STATE_LABELS[state]).toBe("string");
      expect(RUNTIME_STATE_LABELS[state].length).toBeGreaterThan(0);
    }
  });

  it("RUNTIME_STATE_HINT has an entry for every RuntimeState", () => {
    expect(Object.keys(RUNTIME_STATE_HINT).sort()).toEqual([...RUNTIME_STATES].sort());
    for (const state of RUNTIME_STATES) {
      expect(typeof RUNTIME_STATE_HINT[state]).toBe("string");
      expect(RUNTIME_STATE_HINT[state].length).toBeGreaterThan(0);
    }
  });
});
