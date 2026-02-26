import { runOp } from "../runner";

export function registerHealth(api: { registerCommand: (c: unknown) => void }) {
  api.registerCommand({
    name: "health",
    description: "System health check. Usage: /health",
    acceptsArgs: false,
    requireAuth: true,
    handler: async () => {
      try {
        const result = runOp(["healthcheck"]);
        const h = JSON.parse(result) as {
          healthy?: boolean;
          disk_used_pct?: number;
          load_1m?: string;
          jobs_total?: number;
          jobs_failed?: number;
          jobs_running?: number;
          policy?: string;
          recent_failures?: string[];
        };
        const status = h.healthy ? "HEALTHY" : "DEGRADED";
        let msg = `System: ${status}\n`;
        msg += `Disk: ${h.disk_used_pct}%\n`;
        msg += `Load: ${h.load_1m ?? "n/a"}\n`;
        msg += `Jobs: ${h.jobs_total} total, ${h.jobs_failed} failed, ${h.jobs_running} running\n`;
        msg += `Policy: ${h.policy}`;
        if (h.recent_failures?.length) {
          msg += `\n\nRecent failures:\n${h.recent_failures.map((f: string) => `  - ${f}`).join("\n")}`;
        }
        return { text: msg };
      } catch (e: unknown) {
        return { text: `Health check failed: ${(e as Error).message}` };
      }
    },
  });
}
