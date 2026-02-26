import { execFileSync } from "node:child_process";
import { existsSync, readFileSync, readdirSync } from "node:fs";
import { join } from "node:path";
import { OPERATOR_ROOT, runOp, readFileSafe } from "../runner";

const researchProjectIdRe = /^proj-[a-zA-Z0-9-]+$/;

function validateProjectId(id: string): string | null {
  const s = (id || "").trim().split(/\s+/)[0];
  return s && researchProjectIdRe.test(s) ? s : null;
}

export function registerResearch(api: { registerCommand: (c: unknown) => void }) {
  api.registerCommand({
    name: "research-feedback",
    description: "Send feedback for a research project. Usage: /research-feedback <project_id> <dig_deeper|wrong|excellent|ignore> [comment]. Or: /research-feedback <project_id> redirect \"new question\"",
    acceptsArgs: true,
    requireAuth: true,
    handler: async (ctx: { args?: string }) => {
      const raw = (ctx.args || "").trim();
      if (!raw) return { text: "Usage: /research-feedback <project_id> <type> [comment]\ntype: dig_deeper | wrong | excellent | ignore | redirect" };
      try {
        const parts = raw.split(/\s+/);
        const projectId = parts[0] || "";
        const fbType = parts[1] || "";
        const comment = parts.slice(2).join(" ");
        const args = comment
          ? ["/root/operator/tools/research_feedback.py", projectId, fbType, comment]
          : ["/root/operator/tools/research_feedback.py", projectId, fbType];
        const out = execFileSync("python3", args, {
          encoding: "utf8",
          timeout: 15_000,
        }).trim();
        const data = JSON.parse(out) as { ok?: boolean; type?: string };
        if (data.ok) {
          return { text: `Feedback recorded: ${data.type}${data.type === "redirect" ? " (question added)" : ""}.` };
        }
        return { text: out };
      } catch (e: unknown) {
        return { text: `Feedback failed: ${(e as Error).message}` };
      }
    },
  });

  api.registerCommand({
    name: "research-start",
    description: "Start a new research project. Usage: /research-start <question>",
    acceptsArgs: true,
    requireAuth: true,
    handler: async (ctx: { args?: string }) => {
      const question = (ctx.args || "").trim();
      if (!question) return { text: "Usage: /research-start <Frage>\nBeispiel: /research-start Wie ist der Stand bei Feststoffbatterien?" };
      try {
        const jobDir = runOp(["job", "new", "--workflow", "research-init", "--request", question], 10_000);
        runOp(["run", jobDir], 120_000);
        const projectId = readFileSafe(join(jobDir, "artifacts", "project_id.txt")).trim();
        if (!projectId) throw new Error("Keine project_id in artifacts.");
        return {
          text: `Projekt angelegt: ${projectId}\n\nNächster Schritt: /research-cycle ${projectId}\n(mehrmals ausführen bis Phase „done“, oder /research-go nutzen)`,
        };
      } catch (e: unknown) {
        return { text: `Research-Start fehlgeschlagen: ${(e as Error).message}` };
      }
    },
  });

  api.registerCommand({
    name: "research-cycle",
    description: "Run one research cycle for a project. Usage: /research-cycle <project_id>",
    acceptsArgs: true,
    requireAuth: true,
    handler: async (ctx: { args?: string }) => {
      const projectId = validateProjectId(ctx.args || "");
      if (!projectId) return { text: "Usage: /research-cycle <project_id>\nBeispiel: /research-cycle proj-20260225-654f85b2" };
      try {
        const jobDir = runOp(["job", "new", "--workflow", "research-cycle", "--request", projectId], 10_000);
        runOp(["run", jobDir], 300_000);
        const projectPath = join(OPERATOR_ROOT, "research", projectId, "project.json");
        let phase = "?";
        if (existsSync(projectPath)) {
          try {
            const data = JSON.parse(readFileSync(projectPath, "utf8")) as { phase?: string; status?: string };
            phase = data.phase || "?";
            const status = data.status || "?";
            if (phase === "done") {
              return { text: `Forschung abgeschlossen (${projectId}). Report in research/${projectId}/reports/` };
            }
            return { text: `Phase: ${phase} (Status: ${status}). Nächster Lauf: /research-cycle ${projectId}` };
          } catch {
            // ignore
          }
        }
        return { text: `Cycle ausgeführt. Projekt: ${projectId}, Phase: ${phase}.` };
      } catch (e: unknown) {
        return { text: `Research-Cycle fehlgeschlagen: ${(e as Error).message}` };
      }
    },
  });

  api.registerCommand({
    name: "research-go",
    description: "Start research; runs one cycle every 6h for up to 14 days (background). Usage: /research-go <question>",
    acceptsArgs: true,
    requireAuth: true,
    handler: async (ctx: { args?: string }) => {
      const question = (ctx.args || "").trim();
      if (!question) return { text: "Usage: /research-go <Frage>\nBeispiel: /research-go Wie ist der Stand bei Feststoffbatterien?" };
      try {
        const jobDir = runOp(["job", "new", "--workflow", "research-init", "--request", question], 10_000);
        runOp(["run", jobDir], 120_000);
        const projectId = readFileSafe(join(jobDir, "artifacts", "project_id.txt")).trim();
        if (!projectId) throw new Error("Keine project_id in artifacts.");
        const { spawn } = await import("node:child_process");
        const script = join(OPERATOR_ROOT, "tools", "run-research-over-days.sh");
        spawn("bash", [script, projectId, "6", "14"], {
          cwd: OPERATOR_ROOT,
          detached: true,
          stdio: "ignore",
        }).unref();
        return {
          text: `Research gestartet (läuft über Tage im Hintergrund).\nProjekt: ${projectId}\nZyklus alle 6h, max. 14 Tage.\n\nStatus: /research-status ${projectId}\nLog: research/${projectId}/over-days.log`,
        };
      } catch (e: unknown) {
        return { text: `Research-Go fehlgeschlagen: ${(e as Error).message}` };
      }
    },
  });

  api.registerCommand({
    name: "research-status",
    description: "Show research project status. Usage: /research-status <project_id>",
    acceptsArgs: true,
    requireAuth: true,
    handler: async (ctx: { args?: string }) => {
      const projectId = validateProjectId(ctx.args || "");
      if (!projectId) return { text: "Usage: /research-status <project_id>" };
      try {
        const projectPath = join(OPERATOR_ROOT, "research", projectId, "project.json");
        if (!existsSync(projectPath)) return { text: `Projekt nicht gefunden: ${projectId}` };
        const data = JSON.parse(readFileSync(projectPath, "utf8")) as { phase?: string; status?: string; question?: string };
        const phase = data.phase || "?";
        const status = data.status || "?";
        const question = (data.question || "").slice(0, 60) + ((data.question || "").length > 60 ? "…" : "");
        let reports = "";
        try {
          const reportsDir = join(OPERATOR_ROOT, "research", projectId, "reports");
          if (existsSync(reportsDir)) {
            const files = readdirSync(reportsDir).filter((f: string) => f.endsWith(".md"));
            reports = `Reports: ${files.length}`;
          }
        } catch {
          // ignore
        }
        return {
          text: `Projekt: ${projectId}\nFrage: ${question}\nPhase: ${phase}\nStatus: ${status}\n${reports}`,
        };
      } catch (e: unknown) {
        return { text: `Status fehlgeschlagen: ${(e as Error).message}` };
      }
    },
  });
}
