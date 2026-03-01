import { NextRequest, NextResponse } from "next/server";
import { readFile } from "fs/promises";
import { spawn } from "child_process";
import path from "path";
import { getSession } from "@/lib/auth/session";
import { getMasterReportPdf } from "@/lib/operator/research";
import { existsSync } from "fs";
import { OPERATOR_ROOT } from "@/lib/operator/config";

export const dynamic = "force-dynamic";

const MASTER_PDF_SCRIPT = path.join(OPERATOR_ROOT, "tools", "research_pdf_master.py");
const VENV_PYTHON = path.join(OPERATOR_ROOT, ".venv", "bin", "python3");
function getPython(): string {
  return existsSync(VENV_PYTHON) ? VENV_PYTHON : "python3";
}

/** Generate Master Dossier PDF if missing; return PDF file. */
export async function GET(
  _request: NextRequest,
  { params }: { params: Promise<{ id: string }> }
) {
  const ok = await getSession();
  if (!ok) return NextResponse.json({ error: "Unauthorized" }, { status: 401 });
  const id = (await params).id;
  if (!id) return NextResponse.json({ error: "Missing id" }, { status: 400 });

  let pdf = await getMasterReportPdf(id);
  if (!pdf) {
    const masterMd = path.join(OPERATOR_ROOT, "research", id, "MASTER_DOSSIER.md");
    if (!existsSync(masterMd)) {
      return NextResponse.json({ error: "No Master Dossier (MASTER_DOSSIER.md)" }, { status: 404 });
    }
    const proc = spawn(getPython(), [MASTER_PDF_SCRIPT, id], {
      cwd: OPERATOR_ROOT,
      env: { ...process.env, PYTHONPATH: OPERATOR_ROOT },
    });
    await new Promise<void>((resolve, reject) => {
      proc.on("close", (code) => (code === 0 ? resolve() : reject(new Error(`Exit ${code}`))));
      proc.on("error", reject);
    }).catch(() => undefined);
    pdf = await getMasterReportPdf(id);
  }

  if (!pdf) {
    return NextResponse.json(
      { error: "Master PDF not available. Install weasyprint and markdown: pip install weasyprint markdown" },
      { status: 422 }
    );
  }

  const buffer = await readFile(pdf.path);
  return new Response(buffer, {
    headers: {
      "Content-Type": "application/pdf",
      "Content-Disposition": `attachment; filename="${pdf.filename}"`,
    },
  });
}
