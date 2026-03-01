# Autonomous Scientist V2 - Masterplan

Dieses Dokument beschreibt die Architektur-Erweiterung des Operator-Systems von einer linearen "Research & Report"-Pipeline zu einem rekursiven, Code-ausführenden "Autonomous Scientist".

## Kern-Philosophie
1. **Tester, nicht nur Talker:** Die KI muss ihre Theorien durch echten Code beweisen können.
2. **Kontrollierte Fraktale:** Wenn Wissen fehlt, spawnt das System Sub-Agenten – aber unter strengen Guardrails (Tiefe, Budget, Scope).
3. **Selbst-Evolution:** Das System lernt nicht nur Fakten, sondern optimiert seine eigenen Prompts (Auto-Prompt-Optimization).

---

## Phase 1: Die "Proof of Concept" Code-Sandbox (Sicherheit & Execution)
Damit die KI echten Code ausführen kann, ohne den Hetzner-Server zu gefährden, brauchen wir eine isolierte Umgebung.

* **Tool:** `tools/research_sandbox.py`
* **Mechanismus:** 
  * Nutzt die Docker-Engine (z.B. `docker run --rm -v ... python:3.11-slim`).
  * Harte Limits: `max_memory=512m`, `cpus=1`, `timeout=60s`.
  * Kein oder stark eingeschränkter Netzwerkzugriff für den generierten Code.
* **Input:** Python-Code (als String generiert vom LLM).
* **Output:** `stdout`, `stderr`, Exit-Code.

## Phase 2: Die Trial-&-Error Schleife (Der Forscher-Loop)
Integration in die Forschungspipeline, direkt *nach* der `Synthesize`-Phase, wenn die Confidence einer These noch "unbewiesene Fakten" (`? > 0`) aufweist.

* **Neuer Workflow-Schritt:** `research_experiment.py`
* **Ablauf:**
  1. Das LLM bekommt seine eigene Synthese und die Aufgabe: "Beweise These X durch ein isoliertes Python-Skript".
  2. Der Code wird an die Sandbox (Phase 1) übergeben.
  3. **Loop:** Wenn der Code crasht (Exit-Code != 0), wird der `stderr` (Error-Log) zusammen mit dem alten Code zurück an das LLM geschickt: "Dein Code ist fehlgeschlagen mit Error Y. Fixe ihn."
  4. **Abbruch:** Max 5-10 Iterationen. Danach wird das Experiment entweder als `Verified` oder `Failed` im Claim-Ledger verbucht.

## Phase 3: Fraktale Sub-Agenten (Das Mikroskop)
Wenn der Agent im Forscher-Loop feststeckt, darf er Hilfe holen.

* **Architektur:** Ein modifizierter Aufruf von `bin/operator run`.
* **Guardrails (Zwingend!):**
  * `MAX_RECURSION_DEPTH = 1`: Ein Sub-Agent darf niemals selbst weitere Agenten spawnen.
  * `MAX_CONCURRENT_AGENTS = 3`: Der Haupt-Agent darf max. 3 Sub-Tasks pro Run starten.
  * **Token Governor Gatekeeper:** Sub-Agenten laufen *immer* auf der `cheap` oder `mid` Lane.
* **Scope-Zwang:** Der Prompt für den Sub-Agenten muss mikroskopisch sein (z.B. "Finde den Syntax-Fehler für Methode X in Lib Y" statt "Forsche über KI").
* **Rückgabe:** Der Sub-Agent liefert ein reines `result.json` an den blockierten Haupt-Agenten zurück.

## Phase 4: Auto-Prompt Optimization (Selbst-Evolution)
Die Überwindung des "Blank Canvas" Problems. Die statischen Prompts (wie `PROMPT_CONNECT_PHASE_WORLDCLASS.md`) werden dynamisch.

* **Mechanismus (im `memory_consolidate.py` Nightly-Job):**
  1. Das System nimmt eine erfolgreiche Run-Episode.
  2. Es nutzt ein LLM, um 3 Variationen des System-Prompts zu generieren (einen präziseren, einen kreativeren, etc.).
  3. **A/B-Testing:** Es simuliert kleine Tasks mit allen 3 Prompts (Mid Lane).
  4. **Kritiker:** Der Critic (Strong Lane, GPT-5.2) bewertet die Outputs.
  5. Der Gewinner-Prompt wird im Memory V2 (`strategy_profiles` oder einer neuen Tabelle `prompt_optimizations`) als neuer "Gold-Standard" für die jeweilige Domäne abgelegt.

---

## Umsetzung-Reihenfolge
Wir bauen das System von innen nach außen: Ohne Sandbox kein Experiment. Ohne Experiment keine Notwendigkeit für Sub-Agenten.

1. [ ] Implementierung `research_sandbox.py` (Docker Wrapper).
2. [ ] Integration der `Experiment`-Phase in den `operator` CLI-Flow.
3. [ ] Einbau der Sub-Agent Spawning-Logik mit Guardrails.
4. [ ] Aufbau des Auto-Prompt-Optimizers im Consolidate-Script.
