import { OP, runOp, runShell, latestFile, readFileSafe, truncate } from "../runner";

export function registerQueue(api: { registerCommand: (c: unknown) => void }) {
  api.registerCommand({
    name: "oqueue",
    description: "Show latest factory queue. Usage: /oqueue",
    acceptsArgs: false,
    requireAuth: true,
    handler: async () => {
      try {
        runShell(
          `${OP} job new --workflow queue-notify --request telegram | xargs -I{} ${OP} run {}`,
          30_000
        );

        const p = latestFile("telegram.txt");
        if (!p) return { text: "No queue found." };

        const msg = readFileSafe(p);
        return { text: msg || "Queue empty." };
      } catch (e: unknown) {
        return { text: `Queue check failed: ${(e as Error).message}` };
      }
    },
  });

  api.registerCommand({
    name: "qrun",
    description: "Run one item from latest queue. Usage: /qrun <index>",
    acceptsArgs: true,
    requireAuth: true,
    handler: async (ctx: { args?: string }) => {
      const idx = (ctx.args || "").trim();
      if (!idx || isNaN(Number(idx))) return { text: "Usage: /qrun <index> (number)" };

      try {
        runShell(
          `RUN_MODE=index RUN_INDEX=${idx} ${OP} job new --workflow queue-run --request telegram | xargs -I{} ${OP} run {}`,
          300_000
        );

        const p = latestFile("ran.md");
        if (!p) return { text: `Started queue item ${idx}. (no result file yet)` };

        return { text: truncate(readFileSafe(p)) };
      } catch (e: unknown) {
        return { text: `Queue run failed: ${(e as Error).message}` };
      }
    },
  });

  api.registerCommand({
    name: "qrunall",
    description: "Run all items from latest queue. Usage: /qrunall",
    acceptsArgs: false,
    requireAuth: true,
    handler: async () => {
      try {
        runShell(
          `RUN_MODE=all ${OP} job new --workflow queue-run --request telegram | xargs -I{} ${OP} run {}`,
          600_000
        );

        const p = latestFile("ran.md");
        if (!p) return { text: "Queue run started. (no result file yet)" };

        return { text: truncate(readFileSafe(p)) };
      } catch (e: unknown) {
        return { text: `Queue run failed: ${(e as Error).message}` };
      }
    },
  });

  api.registerCommand({
    name: "factory",
    description: "Run full factory cycle (discover + match + pack + deliver). Usage: /factory",
    acceptsArgs: false,
    requireAuth: true,
    handler: async () => {
      try {
        const jobDir = runOp(["job", "new", "--workflow", "factory-cycle", "--request", "telegram trigger"]);
        runOp(["run", jobDir], 300_000);

        const p = latestFile("telegram.txt");
        const msg = p ? readFileSafe(p) : "";

        return {
          text: msg
            ? `Factory cycle complete.\n\n${truncate(msg)}`
            : "Factory cycle complete. No delivery generated.",
        };
      } catch (e: unknown) {
        return { text: `Factory cycle failed: ${(e as Error).message}` };
      }
    },
  });

  api.registerCommand({
    name: "skip",
    description: "Acknowledge queue without running. Usage: /skip",
    acceptsArgs: false,
    requireAuth: true,
    handler: async () => {
      return { text: "Queue acknowledged, skipped." };
    },
  });
}
