# Agent-Prompt: Umfassendes Testsystem für den Operator-/Research-/Agent-Stack

**Rolle:** Du bist ein Senior-Test-Ingenieur. Dein Auftrag ist, ein **sehr ausführliches, robustes Testsystem** für das gesamte System zu bauen. Du darfst ruhig **mehrere Stunden** coden. Das Ziel sind **hundert und mehr Tests** überall im System — **ohne Schrott-Tests**. Tests dürfen nicht auf kaputte oder ungeprüfte Dateien/Module bauen: Zuerst muss sichergestellt sein, dass **der zu testende Code und die zu testende Datei funktionieren**, erst dann schreibst du den Test.

---

## 1. Mission und Qualitätsregeln

### Mission
- **Umfang:** Hunderte von Tests (Ziel: deutlich über 100, idealerweise 200+ sinnvolle Tests).
- **Abdeckung:** Gesamtes System — `lib/`, `tools/`, `workflows/`, UI (soweit sinnvoll automatisierbar), Shell-Skripte, Research-Pipeline, Memory, Brain, Jobs, API-Routen.
- **Qualität:** Jeder Test muss **sinnvoll und wartbar** sein. Kein Test, der nur existiert, um eine Zahl zu erhöhen.

### Goldene Regeln (unverhandelbar)
1. **„Test und Datei müssen funktionieren“:** Bevor du einen Test für ein Modul oder eine Datei schreibst, stelle sicher, dass das Modul/die Datei **importierbar** und **grundlegend ausführbar** ist (z.B. keine Syntaxfehler, keine fehlenden Imports, Mindestfunktionalität). Wenn das Modul kaputt ist, repariere es zuerst oder dokumentiere den Defekt und überspringe den Test bis zur Reparatur — schreibe **keinen** Test, der auf einer bekannten kaputten Basis aufsetzt.
2. **Keine Tests auf zufällige oder ungeprüfte Fixture-Dateien:** Wenn ein Test echte Projektordner, JSON-Dateien oder Konfigurationen braucht, nutze **reproduzierbare Fixtures** (z.B. aus `conftest.py`, `tmp_path`, oder klar definierte Testdaten im Repo). Prüfe einmalig, dass die Fixture-Struktur und -Inhalte **valide** sind (z.B. gültiges JSON, vorhandene Keys).
3. **Keine triviale Assertions:** Ein Test wie `assert True` oder `assert 1 == 1` oder ein Import-Test ohne weitere Verhaltensprüfung zählt nicht als sinnvoller Test. Jeder Test soll ein **konkretes Verhalten** (Return-Wert, Side-Effect, Zustand, Fehlerfall) prüfen.
4. **Isolation:** Tests sollen sich nicht gegenseitig beeinflussen. Nutze `tmp_path`, `mock_operator_root`, `tmp_project`, Datenbank-Copies oder Mocks, damit kein Test von Reihenfolge oder globalem Zustand abhängt.
5. **Determinismus:** Keine Tests, die von aktueller Uhrzeit, Zufall (ohne festen Seed), Netzwerk oder nicht-gesetzten Umgebungsvariablen abhängen. Mock externe Abhängigkeiten (APIs, Dateisystem außer Fixtures) wo nötig.

---

## 2. Vorgehen (Reihenfolge einhalten)

### Phase A: Bestand erfassen und Basis absichern
1. **Inventar:** Liste alle testbaren Einheiten auf: Python-Module in `lib/`, `tools/`, relevante Teile von `workflows/`, Shell-Skripte in `bin/`, `tools/*.sh`, UI-Routen/API (z.B. Next.js API Routes).
2. **Basis-Check:** Für jedes Modul, das du testen willst: Import ausführen, ggf. minimale „Smoke“-Ausführung (z.B. eine Funktion mit klaren Eingaben aufrufen). Wenn Import oder Smoke fehlschlägt: Fehler dokumentieren, Modul reparieren oder vorerst aus dem Test-Scope nehmen — **keinen Test darauf bauen**.
3. **Fixtures prüfen:** Bestehende Fixtures in `tests/conftest.py` (z.B. `mock_operator_root`, `tmp_project`) und eventuelle Test-JSON/Test-Projekte prüfen: Sind sie valide und ausreichend? Fehlende Fixtures für Research-Projekte, Jobs, Memory-DB etc. anlegen und einmalig validieren.

### Phase B: Test-Schichten systematisch füllen
- **Unit-Tests (`tests/unit/`, `tests/tools/`):** Pro Modul/Funktion mindestens: Happy-Path, Grenzfälle (leere Eingabe, None, leere Liste), erwartete Fehlerfälle (ungültige Eingabe, fehlende Datei). Pro Modul mehrere Tests, wo die Logik es hergibt.
- **Integration-Tests (`tests/integration/`):** Zusammenspiel mehrerer Module oder mit echter DB/Filesystem (temp): z.B. Research-Phase-Durchläufe, Memory lesen/schreiben, Job-Erstellung und -Status. Auch hier: Zuerst sicherstellen, dass die beteiligten Komponenten und Fixture-Daten funktionieren.
- **Shell-/CLI-Tests (`tests/shell/`, Bats):** `op healthcheck`, `op job status`, research-init/cycle-Skripte mit Mock-Umgebung. Skripte vorher einmal manuell oder in einem Minimal-Run prüfen, ob sie lauffähig sind.
- **Research-/Quality-Gates (`tests/research/`):** Bestehende Quality-Gate- und Red-Team-Tests einordnen; Lücken schließen (z.B. weitere Fail-Codes, Schwellenwerte, Contract-Tests).
- **UI/API (soweit ohne Browser):** API-Routen mit Request/Response testen (z.B. mit Supertest oder direkten Fetch-Aufrufen gegen eine Test-Instanz); Komponenten-Logik isoliert testen. Keine Tests, die von einer laufenden Produktions-UI abhängen.

### Phase C: Dichte und Abdeckung
- Pro wichtiges Modul **mindestens 3–5** Tests (je nach Komplexität mehr). Bei zentralen Modulen (z.B. `lib/memory`, `research_verify`, `research_synthesize`, `research_progress`, Job-Runner) **deutlich mehr**.
- Grenzfälle und Fehlerpfade explizit abdecken: leere Eingaben, fehlende Keys in JSON, ungültige Projekt-IDs, Timeout-Simulation wo möglich.
- Keine Duplikate: Wenn ein Verhalten schon in einem anderen Test abgedeckt ist, keinen zweiten identischen Test hinzufügen — stattdessen andere Eingaben oder andere Aspekte testen.

### Phase D: Sauberkeit und Wartbarkeit
- Klare Test-Namen: `test_<was>_<bedingung>_<erwartung>` (z.B. `test_advance_phase_when_done_returns_without_change`).
- Gemeinsame Setups in Fixtures auslagern; keine langen Copy-Paste-Blöcke in einzelnen Tests.
- Dokumentation: In `tests/README.md` (oder bestehend erweitern) kurz beschreiben: Schichten (unit/integration/shell), wie man alle Tests ausführt, wie Fixtures funktionieren, welche Umgebungsvariablen nötig sind.

---

## 3. Technischer Kontext (dieses Repo)

- **Python:** pytest, `pytest.ini` mit `pythonpath = .`, `testpaths = tests`.
- **Fixtures:** `conftest.py` mit `mock_operator_root`, `tmp_project`; ggf. Memory-DB in temp.
- **Struktur:** `tests/unit/`, `tests/tools/`, `tests/integration/`, `tests/shell/` (Bats), `tests/research/`.
- **Befehle:** `pytest tests/`, ggf. `pytest tests/unit tests/tools`, `bats tests/shell/*.bats`.
- **Wichtige Module:** `lib.memory`, `tools.research_*` (verify, synthesize, progress, advance_phase, quality_gate, sandbox, …), `workflows/research-phase.sh` (über Shell-Tests), `bin/op` (CLI).

---

## 4. Was du explizit nicht tun sollst

- **Keine** Tests schreiben, die auf einem Modul oder einer Datei aufsetzen, die du als „kaputt“ oder „nicht lauffähig“ identifiziert hast, ohne die Basis zu reparieren oder den Test auszusetzen mit klarem Grund.
- **Keine** Tests, die von echten Secrets, echten API-Keys oder Produktionsdaten abhängen.
- **Keine** rein kosmetischen Tests (z.B. nur `assert True` oder nur ein Import).
- **Keine** flaky Tests (z.B. ohne festen Seed bei Zufall, ohne Mock bei Netzwerk).
- **Keine** Zerstörung von echten Daten: Alle Schreibzugriffe in temp-Verzeichnisse oder Test-DBs.

---

## 5. Lieferumfang und Verifikation

Am Ende soll gelten:
- **Anzahl:** Deutlich über 100, idealerweise 200+ sinnvolle Tests.
- **Lauf:** `pytest tests/` (und ggf. Bats für Shell) läuft durch; alle Tests grün (oder explizit als `xfail`/skip markiert mit Begründung).
- **Dokumentation:** Kurze Anleitung in `tests/README.md` (Struktur, Befehle, Fixtures, Hinweise).
- **Checkliste:** Du listest einmal auf: welche Module/Dateien du als „getestet“ betrachtest, welche du bewusst ausgelassen hast (und warum), und ob es noch bekannte Lücken gibt.

Du arbeitest iterativ: Erst Basis und Fixtures absichern, dann Schicht für Schicht Tests ergänzen, ohne kaputte Grundlagen und ohne sinnlose Tests.

---

## 6. Copy-Paste-Einstiegsprompt (für den Agenten)

```
Du baust ein sehr ausführliches Testsystem für den gesamten Operator-/Research-/Agent-Stack in diesem Repo. Du darfst mehrere Stunden coden.

Ziele:
- Hunderte von Tests (Ziel 200+) überall: lib/, tools/, workflows/, shell, research, UI/API wo sinnvoll.
- Keine schlechten Tests: Kein Test darf auf einer kaputten oder ungeprüften Datei/Modul aufsetzen. Bevor du einen Test schreibst, stelle sicher, dass das zu testende Modul importierbar und grundlegend funktionsfähig ist. Wenn etwas kaputt ist, repariere es zuerst oder dokumentiere und überspringe — schreibe keinen Test auf eine bekannte kaputte Basis.
- Fixtures und Daten: Nutze reproduzierbare Testdaten (conftest.py, tmp_path); prüfe einmalig, dass Fixtures valide sind (z.B. gültiges JSON). Keine Tests, die von zufälligen oder ungeprüften Dateien abhängen.
- Jeder Test soll konkretes Verhalten prüfen (Return-Wert, Side-Effect, Fehlerfall) — keine trivialen assert True/Import-Only-Tests. Tests isoliert und deterministisch (Mock extern, fester Seed bei Zufall).

Vorgehen:
1) Inventar der testbaren Einheiten (lib, tools, workflows, shell, UI/API).
2) Pro Modul: Import + minimaler Smoke-Check. Nur wenn das funktioniert, Tests schreiben.
3) Systematisch Unit-, Integration-, Shell- und Research-Tests füllen; pro wichtigem Modul mehrere Tests, Grenzfälle und Fehlerpfade abdecken.
4) tests/README.md mit Struktur, Befehlen (pytest, bats), Fixtures aktualisieren.

Technik: pytest, testpaths=tests, conftest.py mit mock_operator_root/tmp_project. Keine echten Secrets/Produktionsdaten; alle Schreibzugriffe in temp.

Am Ende: pytest tests/ (und bats) läuft durch, alle grün; Liste welche Module getestet sind, welche ausgelassen und warum. Vollständige Anleitung steht in docs/AGENT_PROMPT_TEST_SYSTEM_BUILD.md — arbeite sie strikt ab.
```
