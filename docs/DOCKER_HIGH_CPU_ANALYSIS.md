# Docker High-CPU Container Analysis (Repair-Block 2026-03-07)

**Nur Analyse und dokumentierte sichere Maßnahmen. Keine automatischen Stop/Kill-Aktionen.**

## Erkannte Container

| Container            | Image                            | Mount              | Laufzeit  | CPU (Host) |
|----------------------|-----------------------------------|--------------------|-----------|------------|
| suspicious_murdock   | operator-research-sandbox:latest  | /tmp/tmpc50orp5c→/app | 3+ Tage   | ~99.9%     |
| relaxed_robinson     | python:3.11-slim                  | /tmp/tmpr58mjbaw→/app | 6+ Tage   | ~0%        |

## Herkunft und Zweck

- **suspicious_murdock:** Stammt sehr wahrscheinlich aus **research_sandbox.run_in_sandbox()** (`tools/research_sandbox.py`). Wird von Research-Experiment-/Council-Sandbox-Läufen genutzt: temporäres Verzeichnis, `script.py` (AI-generierter Code), `docker run --rm --network none --memory 512m --cpus 1.0 -v ... script.py`.
- **relaxed_robinson:** Nutzt `python:3.11-slim` (Fallback-Image bei fehlendem operator-research-sandbox). Ebenfalls typisches Muster: temp dir + script.py.

## Warum laufen sie weiter / hohe CPU?

- **Timeout-Verhalten:** In `research_sandbox.py` wird `subprocess.run(..., timeout=timeout_seconds)` verwendet. Bei Ablauf des Timeouts wird der **Prozess** `docker run` beendet (SIGKILL), der **Container** läuft unter dockerd jedoch weiter. Es entstehen verwaiste Container.
- **suspicious_murdock (99.9% CPU):** Das im Container laufende `script.py` arbeitet offenbar in einer Endlosschleife oder sehr rechenintensiv; der aufrufende Prozess ist nach Timeout beendet, der Container nicht.
- **relaxed_robinson (0% CPU):** Vermutlich blockiert (I/O, Sleep) oder beendet, Prozess noch vorhanden. Logs der Container waren bei der Prüfung leer.

## Logs

- `docker logs suspicious_murdock` / `docker logs relaxed_robinson`: bei der Prüfung keine Ausgabe (leer oder nicht zugreifbar).

## Sichere Maßnahmen (dokumentiert, keine Ausführung)

1. **Manuell prüfen:**  
   `docker logs suspicious_murdock 2>&1 | tail -200`  
   Falls erkennbar ist, dass nur ein alter Sandbox-Lauf ohne Nutzen läuft, kann nach **manueller Entscheidung** gestoppt werden:  
   `docker stop suspicious_murdock`  
   (Container hat `--rm` nicht mehr wirksam, da er bereits erstellt war; bei Stop wird er entfernt, sofern er mit AutoRemove lief – hier: nein, Name ist generiert.)

2. **Zukünftige Läufe härten (Code-Änderung, nicht in diesem Reparatur-Block umgesetzt):**  
   In `tools/research_sandbox.py`: Container mit festem Namen starten (z. B. `--name sandbox-$(uuid)`), bei `subprocess.TimeoutExpired` zusätzlich `docker kill <name>` ausführen, damit keine verwaisten CPU-Läufer entstehen.

3. **relaxed_robinson:** Geringe Last; Stop nur bei Bedarf und nach gleicher manueller Prüfung.

**Keine automatischen Stop/Kill-Aktionen in diesem Audit durchgeführt.**
