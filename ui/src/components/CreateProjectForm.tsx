"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";

const PLAYBOOKS = [
  { id: "general", label: "Allgemein" },
  { id: "market_analysis", label: "Marktanalyse" },
  { id: "literature_review", label: "Literatur-Review" },
  { id: "patent", label: "Patent-Landscape" },
  { id: "due_diligence", label: "Due Diligence" },
];

export function CreateProjectForm() {
  const router = useRouter();
  const [question, setQuestion] = useState("");
  const [playbookId, setPlaybookId] = useState("general");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError("");
    if (!question.trim()) {
      setError("Bitte eine Forschungsfrage eingeben.");
      return;
    }
    setLoading(true);
    try {
      const res = await fetch("/api/research/projects", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ question: question.trim(), playbook_id: playbookId }),
      });
      const data = await res.json();
      if (!res.ok) {
        setError(data.error ?? "Fehlgeschlagen");
        return;
      }
      if (data.ok) {
        router.refresh();
        setQuestion("");
        setError("");
      }
    } catch (e) {
      setError(String((e as Error).message));
    } finally {
      setLoading(false);
    }
  }

  return (
    <form onSubmit={handleSubmit} className="tron-panel space-y-5 p-6">
      <div>
        <h2 className="text-xl font-semibold tracking-tight text-tron-text">
          Neues Research-Projekt
        </h2>
        <p className="mt-1 text-sm text-tron-dim">
          Alle Phasen laufen automatisch durch – kein „Nächste Phase“ klicken nötig. Report erscheint, wenn fertig.
        </p>
      </div>
      <div className="space-y-4">
        <div>
          <label htmlFor="question" className="mb-1.5 block text-sm font-medium text-tron-muted">
            Was willst du erforschen?
          </label>
          <textarea
            id="question"
            value={question}
            onChange={(e) => setQuestion(e.target.value)}
            placeholder="z. B. Marktgröße für Vertical SaaS in der EU"
            rows={3}
            className="w-full rounded-sm border-2 border-tron-border bg-tron-bg px-4 py-3 text-sm text-tron-text placeholder-tron-dim focus:border-tron-accent focus:outline-none focus:shadow-[0_0_15px_var(--tron-glow)] transition-all"
            disabled={loading}
          />
        </div>
        <div>
          <label htmlFor="playbook" className="mb-1.5 block text-sm font-medium text-tron-muted">
            Playbook
          </label>
          <select
            id="playbook"
            value={playbookId}
            onChange={(e) => setPlaybookId(e.target.value)}
            className="w-full rounded-sm border-2 border-tron-border bg-tron-bg px-4 py-3 text-sm text-tron-text focus:border-tron-accent focus:outline-none focus:shadow-[0_0_15px_var(--tron-glow)] transition-all appearance-none"
            disabled={loading}
          >
            {PLAYBOOKS.map((p) => (
              <option key={p.id} value={p.id} className="bg-tron-bg text-tron-text">
                {p.label}
              </option>
            ))}
          </select>
        </div>
      </div>
      {error && <p className="text-sm font-medium text-tron-error">{error}</p>}
      <div className="pt-2">
        <button
          type="submit"
          disabled={loading}
          className="flex h-11 w-full items-center justify-center rounded-sm bg-transparent border-2 border-tron-accent px-4 font-bold text-tron-accent shadow-[0_0_15px_var(--tron-glow)] transition-all hover:bg-tron-accent hover:text-black hover:shadow-[0_0_25px_var(--tron-glow)] active:scale-[0.98] disabled:pointer-events-none disabled:opacity-50 sm:w-auto uppercase tracking-widest"
        >
          {loading ? "Init läuft, bitte kurz warten…" : "Forschung starten"}
        </button>
      </div>
    </form>
  );
}
