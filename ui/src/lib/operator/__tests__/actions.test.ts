import { beforeEach, describe, expect, it, vi } from "vitest";
import { mkdir, readFile, rm, writeFile } from "fs/promises";
import path from "path";

const OPERATOR_ROOT = "/tmp/operator-root";
const CONTROL_PLANE_INTAKE = path.join(OPERATOR_ROOT, "tools", "control_plane_intake.py");
const CAPTURE_FILE = path.join(OPERATOR_ROOT, "control-plane-calls.jsonl");

vi.mock("@/lib/operator/config", () => ({ OPERATOR_ROOT }));

describe("actions (data layer)", () => {
  beforeEach(async () => {
    vi.resetModules();
    await rm(OPERATOR_ROOT, { recursive: true, force: true });
    await mkdir(path.dirname(CONTROL_PLANE_INTAKE), { recursive: true });
    await writeFile(
      CONTROL_PLANE_INTAKE,
      `#!/usr/bin/env python3
import json
import sys
from pathlib import Path

root = Path(${JSON.stringify(OPERATOR_ROOT)})
capture = root / "control-plane-calls.jsonl"
capture.parent.mkdir(parents=True, exist_ok=True)
with capture.open("a", encoding="utf-8") as handle:
    handle.write(json.dumps(sys.argv[1:]) + "\\n")

args = sys.argv[1:]
command = args[0]
if command == "ui-research-continue":
    project_id = args[args.index("--project-id") + 1]
    print(json.dumps({"ok": True, "jobId": project_id, "projectId": project_id, "requestEventId": "evt-continue"}))
elif command == "ui-research-start":
    question = args[args.index("--question") + 1]
    mode = args[args.index("--research-mode") + 1]
    run_until_done = args[args.index("--run-until-done") + 1]
    print(json.dumps({
        "ok": True,
        "jobId": "job-1",
        "projectId": "proj-1",
        "requestEventId": f"evt-start-{mode}-{run_until_done}",
        "question": question,
    }))
else:
    print(json.dumps({"ok": False, "error": f"unknown command: {command}"}))
    raise SystemExit(1)
`,
      { encoding: "utf-8", mode: 0o755 }
    );
  });

  it("runWorkflow returns error for disallowed workflow", async () => {
    const { runWorkflow } = await import("../actions");
    const result = await runWorkflow("disallowed-workflow-id");
    expect(result.ok).toBe(false);
    expect(result.error).toContain("not allowed");
  });

  it("runWorkflow allows research-init", async () => {
    const { ALLOWED_WORKFLOWS } = await import("../actions");
    expect(ALLOWED_WORKFLOWS.has("research-init")).toBe(true);
  });

  it("runWorkflow routes research-cycle through control-plane intake", async () => {
    const { runWorkflow } = await import("../actions");
    const result = await runWorkflow("research-cycle", "proj-1");

    expect(result.ok).toBe(true);
    expect(result.projectId).toBe("proj-1");
    const calls = (await readFile(CAPTURE_FILE, "utf-8")).trim().split("\n").map((line) => JSON.parse(line));
    expect(calls).toEqual([["ui-research-continue", "--project-id", "proj-1"]]);
  });

  it("submitResearchStartIntent uses canonical intake", async () => {
    const { submitResearchStartIntent } = await import("../actions");
    const result = await submitResearchStartIntent("Question?", "discovery", true);

    expect(result.ok).toBe(true);
    expect(result.projectId).toBe("proj-1");
    const calls = (await readFile(CAPTURE_FILE, "utf-8")).trim().split("\n").map((line) => JSON.parse(line));
    expect(calls).toEqual([
      [
        "ui-research-start",
        "--question",
        "Question?",
        "--research-mode",
        "discovery",
        "--run-until-done",
        "1",
      ],
    ]);
  });
});
