import { makeRequest, runDispatch, runOp } from "../runner";

export function registerJobs(api: { registerCommand: (c: unknown) => void }) {
  api.registerCommand({
    name: "do",
    description: "Create an operator job (plan-only). Usage: /do <text>",
    acceptsArgs: true,
    requireAuth: true,
    handler: async (ctx: { args?: string }) => {
      const text = (ctx.args || "").trim();
      if (!text) return { text: "Usage: /do <text>" };

      try {
        const reqPath = makeRequest("planner", text);
        const jobId = runDispatch(["create", "--request", reqPath]);

        return {
          text:
            `Job created: ${jobId}\n\n` +
            `Commands:\n` +
            `  /run ${jobId}\n` +
            `  /job-status ${jobId}\n` +
            `  /job-artifacts ${jobId}`,
        };
      } catch (e: unknown) {
        return { text: `Failed to create job: ${(e as Error).message}` };
      }
    },
  });

  api.registerCommand({
    name: "run",
    description: "Run an operator job. Usage: /run <job_id>",
    acceptsArgs: true,
    requireAuth: true,
    handler: async (ctx: { args?: string }) => {
      const jobId = (ctx.args || "").trim();
      if (!jobId) return { text: "Usage: /run <job_id>" };

      try {
        const status = runDispatch(["run", jobId], 300_000);
        return { text: `Job ${jobId}: ${status}` };
      } catch (e: unknown) {
        return { text: `Run failed: ${(e as Error).message}` };
      }
    },
  });

  api.registerCommand({
    name: "job-status",
    description: "Get job status. Usage: /job-status [job_id]",
    acceptsArgs: true,
    requireAuth: true,
    handler: async (ctx: { args?: string }) => {
      const jobId = (ctx.args || "").trim();

      try {
        if (!jobId) {
          const list = runOp(["job", "status", "--limit", "10"]);
          return { text: list ? `Recent jobs:\n\n${list}` : "No jobs found." };
        }

        const status = runDispatch(["status", jobId]);
        return { text: `${jobId}: ${status}` };
      } catch (e: unknown) {
        return { text: `Status check failed: ${(e as Error).message}` };
      }
    },
  });

  api.registerCommand({
    name: "job-artifacts",
    description: "List job artifacts. Usage: /job-artifacts <job_id>",
    acceptsArgs: true,
    requireAuth: true,
    handler: async (ctx: { args?: string }) => {
      const jobId = (ctx.args || "").trim();
      if (!jobId) return { text: "Usage: /job-artifacts <job_id>" };

      try {
        const files = runDispatch(["artifacts", jobId]);
        return { text: files ? `Artifacts:\n${files}` : "No artifacts." };
      } catch (e: unknown) {
        return { text: `Failed: ${(e as Error).message}` };
      }
    },
  });
}
