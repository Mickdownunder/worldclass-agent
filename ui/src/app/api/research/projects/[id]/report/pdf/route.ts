import { NextRequest, NextResponse } from "next/server";
import { readFile } from "fs/promises";
import { spawn } from "child_process";
import path from "path";
import { getSession } from "@/lib/auth/session";
import { getLatestReportPdf } from "@/lib/operator/research";
import { existsSync } from "fs";
import { OPERATOR_ROOT } from "@/lib/operator/config";

export const dynamic = "force-dynamic";

const PDF_SCRIPT = path.join(OPERATOR_ROOT, "tools", "research_pdf_report.py");
const VENV_PYTHON = path.join(OPERATOR_ROOT, ".venv", "bin", "python3");
function getPythonForPdf(): string {
  return existsSync(VENV_PYTHON) ? VENV_PYTHON : "python3";
}

export async function GET(
  _request: NextRequest,
  { params }: { params: Promise<{ id: string }> }
) {
  const ok = await getSession();
  if (!ok) return NextResponse.json({ error: "Unauthorized" }, { status: 401 });
  const id = (await params).id;
  if (!id) return NextResponse.json({ error: "Missing id" }, { status: 400 });
  try {
    const pdf = await getLatestReportPdf(id);
    if (!pdf) return NextResponse.json({ error: "No PDF report yet" }, { status: 404 });
    const buffer = await readFile(pdf.path);
    const filename = `report-${id}.pdf`;
    return new Response(buffer, {
      headers: {
        "Content-Type": "application/pdf",
        "Content-Disposition": `attachment; filename="${filename}"`,
      },
    });
  } catch (e) {
    return NextResponse.json(
      { error: String((e as Error).message) },
      { status: 500 }
    );
  }
}

/** Generate PDF from latest report markdown (e.g. when job skipped PDF due to missing weasyprint). */
export async function POST(
  _request: NextRequest,
  { params }: { params: Promise<{ id: string }> }
) {
  const ok = await getSession();
  if (!ok) return NextResponse.json({ error: "Unauthorized" }, { status: 401 });
  const id = (await params).id;
  if (!id) return NextResponse.json({ error: "Missing id" }, { status: 400 });
  return new Promise<NextResponse>((resolve) => {
    const proc = spawn(getPythonForPdf(), [PDF_SCRIPT, id], {
      cwd: OPERATOR_ROOT,
      env: { ...process.env, PYTHONPATH: OPERATOR_ROOT },
    });
    let stderr = "";
    proc.stderr?.on("data", (c) => { stderr += c.toString(); });
    proc.on("close", (code) => {
      if (code === 0) {
        resolve(NextResponse.json({ ok: true }));
      } else {
        const msg = (stderr || `Exit code ${code}`).trim().slice(0, 400);
        resolve(NextResponse.json({ error: msg || "PDF generation failed" }, { status: 422 }));
      }
    });
    proc.on("error", (e) => {
      resolve(NextResponse.json({ error: String(e.message) }, { status: 500 }));
    });
  });
}
