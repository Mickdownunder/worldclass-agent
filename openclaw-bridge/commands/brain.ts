import { runShell, truncate } from "../runner";

export function registerBrain(api: { registerCommand: (c: unknown) => void }) {
  api.registerCommand({
    name: "think",
    description: "Ask the brain to think about a goal. Usage: /think <goal>",
    acceptsArgs: true,
    requireAuth: true,
    handler: async (ctx: { args?: string }) => {
      const goal = (ctx.args || "").trim() || "Decide the most impactful next action";
      try {
        const result = runShell(
          `source /root/operator/conf/secrets.env 2>/dev/null; /root/operator/bin/brain think --goal '${goal.replace(/'/g, "'\\''")}'`,
          120_000
        );
        const plan = JSON.parse(result) as {
          analysis?: string;
          confidence?: string;
          plan?: Array< { urgency?: string; action?: string; reason?: string }>;
          risks?: string[];
        };
        let msg = `Brain Analysis:\n${plan.analysis || "none"}\n\nConfidence: ${plan.confidence || "?"}\n\nPlan:`;
        for (const a of plan.plan || []) {
          msg += `\n- [${a.urgency || "?"}] ${a.action}: ${a.reason || ""}`;
        }
        if (plan.risks?.length) {
          msg += `\n\nRisks:\n${plan.risks.map((r: string) => `- ${r}`).join("\n")}`;
        }
        return { text: truncate(msg) };
      } catch (e: unknown) {
        return { text: `Think failed: ${(e as Error).message}` };
      }
    },
  });

  api.registerCommand({
    name: "cycle",
    description: "Run a full cognitive cycle. Usage: /cycle [goal]",
    acceptsArgs: true,
    requireAuth: true,
    handler: async (ctx: { args?: string }) => {
      const goal = (ctx.args || "").trim() || "Decide and execute the most impactful next action";
      try {
        const result = runShell(
          `source /root/operator/conf/secrets.env 2>/dev/null; /root/operator/bin/brain cycle --goal '${goal.replace(/'/g, "'\\''")}'`,
          300_000
        );
        const cycle = JSON.parse(result) as {
          decision?: string;
          status?: string;
          quality?: string;
          executed?: boolean;
          learnings?: string;
          should_retry?: boolean;
        };
        let msg = `Cognitive Cycle Complete\n\n`;
        msg += `Decision: ${cycle.decision || "none"}\n`;
        msg += `Status: ${cycle.status || "?"}\n`;
        msg += `Quality: ${cycle.quality || "?"}\n`;
        msg += `Executed: ${cycle.executed ? "yes" : "no"}\n`;
        if (cycle.learnings) msg += `\nLearnings: ${cycle.learnings}`;
        if (cycle.should_retry) msg += `\n\nShould retry: yes`;
        return { text: truncate(msg) };
      } catch (e: unknown) {
        return { text: `Cycle failed: ${(e as Error).message}` };
      }
    },
  });

  api.registerCommand({
    name: "memory",
    description: "Query agent memory. Usage: /memory [search query]",
    acceptsArgs: true,
    requireAuth: true,
    handler: async (ctx: { args?: string }) => {
      const query = (ctx.args || "").trim();
      try {
        const args = query ? `--query '${query.replace(/'/g, "'\\''")}'` : "";
        const result = runShell(`/root/operator/bin/brain memory ${args}`, 10_000);
        const data = JSON.parse(result) as {
          episodes?: Array<{ kind?: string; content?: string }>;
          reflections?: Array<{ quality?: string; learnings?: string }>;
          totals?: { episodes?: number; decisions?: number; reflections?: number; avg_quality?: number };
          playbooks?: Array<{ domain?: string; strategy?: string }>;
        };
        if (query) {
          const eps = (data.episodes || []).slice(0, 5);
          const refs = (data.reflections || []).slice(0, 3);
          let msg = `Memory search: "${query}"\n\nEpisodes (${eps.length}):`;
          for (const e of eps) msg += `\n- [${e.kind}] ${e.content?.slice(0, 100)}`;
          if (refs.length) {
            msg += `\n\nReflections (${refs.length}):`;
            for (const r of refs) msg += `\n- [q=${r.quality}] ${r.learnings?.slice(0, 100)}`;
          }
          return { text: truncate(msg) };
        } else {
          const t = data.totals || {};
          let msg = `Memory State\n\n`;
          msg += `Episodes: ${t.episodes || 0}\n`;
          msg += `Decisions: ${t.decisions || 0}\n`;
          msg += `Reflections: ${t.reflections || 0}\n`;
          msg += `Avg Quality: ${t.avg_quality || 0}\n`;
          if (data.playbooks?.length) {
            msg += `\nPlaybooks (${data.playbooks.length}):`;
            for (const p of data.playbooks) msg += `\n- ${p.domain}: ${p.strategy?.slice(0, 80)}`;
          }
          return { text: truncate(msg) };
        }
      } catch (e: unknown) {
        return { text: `Memory query failed: ${(e as Error).message}` };
      }
    },
  });
}
