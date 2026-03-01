# Provider-Fallback bei Quota/Bottleneck (429)

Das Research-System kann bei **429 / Quota** automatisch den **anderen LLM-Provider** nutzen, damit Läufe nicht abbrechen.

## Aktivierung

- **Env:** `RESEARCH_LLM_FALLBACK_ON_QUOTA=1` (oder `true`/`yes`).
- **Default:** Aus (0). Ohne Setzen bleibt Verhalten wie bisher (Fehler nach Retries).

## Ablauf

1. `research_common.llm_call(model, ...)` versucht zuerst den angeforderten Model (OpenAI oder Gemini).
2. Nach allen Retries: wenn der Fehler **Quota/429** ist und Fallback aktiv ist, wird **einmal** der andere Provider versucht:
   - **OpenAI (gpt-*)** → Fallback **Gemini** (Default: `gemini-2.5-flash`), wenn `GEMINI_API_KEY` gesetzt.
   - **Gemini (gemini-*)** → Fallback **OpenAI** (Default: `gpt-4.1-mini`), wenn `OPENAI_API_KEY` gesetzt.
3. Stderr-Log: `research_common: provider fallback (quota/429) <model> -> <fallback>`.
4. Budget wird unter dem **tatsächlich genutzten** Model gebucht (Fallback-Model).

## Konfiguration

| Env | Bedeutung |
|-----|-----------|
| `RESEARCH_LLM_FALLBACK_ON_QUOTA` | 1 = bei Quota/429 anderen Provider versuchen |
| `RESEARCH_LLM_FALLBACK_GEMINI` | Fallback-Model bei OpenAI-Quota (Default: gemini-2.5-flash) |
| `RESEARCH_LLM_FALLBACK_OPENAI` | Fallback-Model bei Gemini-Quota (Default: gpt-4.1-mini) |

## Gilt für

- Alle Aufrufe über **`research_common.llm_call`**: Planner, Verify, Synthesize, Critic, Discovery Analysis, etc.
- **Nicht** automatisch: **Brain** (Reflect) nutzt eigenes `_llm_json`; bei Bedarf dort gleiche Logik einbauen oder Brain auf gemeinsame LLM-Schicht umstellen.

## Ist automatischer Wechsel „schlecht“?

**Nein, wenn bewusst aktiviert:**

- **Vorteile:** Weniger abgebrochene Runs, weniger manuelles Eingreifen, bessere Ausfallsicherheit bei einem überlasteten Provider.
- **Risiken:** (1) **Kosten/Qualität** – Fallback-Model kann andere Preise/Qualität haben; (2) **Reproduzierbarkeit** – bei strikter Reproduktion pro Model besser Fallback aus lassen; (3) **Beide Quotas voll** – dann hilft nur Erhöhung oder Backoff.

**Empfehlung:** Fallback **an** für normale Betriebsumgebung (inkl. Discovery), **aus** wenn du strikt ein einziges Model/Provider pro Run brauchst oder Kosten exakt pro Provider trennen willst.
