import { readFile, readdir } from "fs/promises";
import path from "path";
import { OPERATOR_ROOT } from "./config";

const FACTORY_PACKS = path.join(OPERATOR_ROOT, "factory", "packs");

export interface PackSummary {
  client: string;
  date: string;
  summaryPath: string;
  packJsonPath: string;
  summaryMd?: string;
  packJson?: Record<string, unknown>;
}

export async function listPacks(): Promise<PackSummary[]> {
  const out: PackSummary[] = [];
  try {
    const clientDirs = await readdir(FACTORY_PACKS, { withFileTypes: true });
    for (const cd of clientDirs) {
      if (!cd.isDirectory()) continue;
      const dateDirs = await readdir(path.join(FACTORY_PACKS, cd.name), { withFileTypes: true });
      for (const dd of dateDirs) {
        if (!dd.isDirectory()) continue;
        const base = path.join(FACTORY_PACKS, cd.name, dd.name);
        const packJsonPath = path.join(base, "pack.json");
        out.push({
          client: cd.name,
          date: dd.name,
          summaryPath: path.join(base, "summary.md"),
          packJsonPath,
        });
      }
    }
    out.sort((a, b) => (b.date + b.client).localeCompare(a.date + a.client));
  } catch {
    //
  }
  return out;
}

export async function getPack(client: string, date: string): Promise<{
  summaryMd?: string;
  packJson?: Record<string, unknown>;
} | null> {
  const base = path.join(FACTORY_PACKS, client, date);
  try {
    const [summaryMd, packJson] = await Promise.all([
      readFile(path.join(base, "summary.md"), "utf-8").catch(() => undefined),
      readFile(path.join(base, "pack.json"), "utf-8")
        .then((s) => JSON.parse(s) as Record<string, unknown>)
        .catch(() => undefined),
    ]);
    return { summaryMd, packJson };
  } catch {
    return null;
  }
}
