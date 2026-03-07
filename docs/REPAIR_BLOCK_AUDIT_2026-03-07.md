# Technischer Reparatur-Block — Audit-Bericht (2026-03-07)

Kompakter Abschlussbericht: durchgeführte Reparaturen, geänderte Dateien, bereinigte Projekte, offene Risiken, Verifikation.

---

## 1. Was wurde gefixt

| # | Punkt | Maßnahme |
|---|--------|----------|
| 1 | **policy.env** | `DENY_CMDS` in Anführungszeichen gesetzt, damit beim Sourcen keine Shell-Fehler entstehen und die Variable vollständig gesetzt bleibt. |
| 2 | **system_monitor.sh** | Load-Check auf reine Exit-Code-Prüfung umgestellt (`awk ... BEGIN { exit (l > t) ? 0 : 1 }`), keine numerische Ausgabe mehr als Befehl → kein „0: command not found“ in monitor.log. |
| 3 | **Research-Lock / Stuck** | Stale-Lock-Recovery in `research-phase.sh` erweitert: neben „pid nicht in /proc“ wird auch `progress.json` mit `alive=false` als verwaist gewertet; dann Lock entfernen und erneut acquiren. |
| 4 | **Stuck/Failed-Projekte** | Einmalige Bereinigung: `.cycle.lock` nur entfernt, wo `progress.json` **alive=false** und (PID leer oder PID nicht in `/proc`). Keine Änderung an `project.json`-Status, keine blinden Löschaktionen. |
| 5 | **Docker High-CPU** | Nur Analyse und Dokumentation: Herkunft (research_sandbox), Zweck (script.py), Grund für Verwaiste (Timeout tötet `docker run`, Container läuft weiter). Sichere Optionen in `docs/DOCKER_HIGH_CPU_ANALYSIS.md` beschrieben; **keine** automatischen Stop/Kill-Aktionen. |

---

## 2. Geänderte Dateien

| Datei | Änderung |
|-------|----------|
| `operator/conf/policy.env` | Zeile 5: `DENY_CMDS="rm,mv,...,systemctl restart,systemctl stop,chmod,chown"` (ganzer Wert in Anführungszeichen). |
| `operator/tools/system_monitor.sh` | Zeile 16–18: Load-Vergleich nur noch per `awk`-Exit-Code, kein `$(...)`-Ausführung. |
| `operator/workflows/research-phase.sh` | Lock-Recovery-Block: `progress_alive` aus `progress.json` lesen; Recovery wenn `prev_pid` tot **oder** `progress_alive=false`; dann `rm -f` Lock und erneuter Acquire. |
| `operator/docs/DOCKER_HIGH_CPU_ANALYSIS.md` | Neu: Analyse der High-CPU-Container, Herkunft, sichere Maßnahmen (nur dokumentiert). |
| `operator/docs/REPAIR_BLOCK_AUDIT_2026-03-07.md` | Dieser Bericht. |

---

## 3. Bereinigte Projekte (nur Lock-Cleanup)

**.cycle.lock entfernt** bei allen Projekten, die **alive=false** und (keine PID oder PID nicht in `/proc`) hatten. Davon betroffen u. a.:

- proj-20260307-c1d43501  
- proj-20260302-* (mehrere)  
- proj-20260301-* (mehrere)  
- proj-20260228-867f50e1  

**Nicht geändert:** `project.json` (z. B. Status `failed_stuck_phase` bleibt; nur Lock wurde entfernt, damit ein neuer Cycle ggf. starten kann).

---

## 4. Offen bleibende Risiken

- **Secrets:** `conf/secrets.env` und UI `.env.local` weiterhin Klartext; `FORCE_INSECURE_COOKIE=1` in Produktion vermeiden.  
- **Docker-Verwaiste:** `suspicious_murdock` (99.9 % CPU) und `relaxed_robinson` laufen weiter; Stopp nur nach manueller Prüfung empfohlen (siehe DOCKER_HIGH_CPU_ANALYSIS.md).  
- **Sandbox-Timeout:** In `research_sandbox.py` bei Timeout den Container gezielt per Namen killen (noch nicht umgesetzt).  
- **206 fehlgeschlagene Jobs:** Keine automatische Nachanalyse; bei Bedarf manuell auswerten.

---

## 5. Ausgeführte Verifikationen

```bash
# policy.env: Sourcen ohne Fehler, DENY_CMDS gesetzt
cd /root/operator && source conf/policy.env 2>&1; echo "DENY_CMDS set: ${DENY_CMDS:+yes}"
# Erwartung: keine Fehler, "DENY_CMDS set: yes"

# system_monitor.sh: Syntax und ein Lauf ohne "0: command not found"
bash -n /root/operator/tools/system_monitor.sh && /root/operator/tools/system_monitor.sh
# Erwartung: syntax OK, exit 0, keine "0: command not found"-Zeile

# Healthcheck
./bin/op healthcheck
# Erwartung: "healthy": true

# Lock für c1d43501 entfernt
ls /root/operator/research/proj-20260307-c1d43501/.cycle.lock
# Erwartung: No such file or directory
```

Alle genannten Checks wurden ausgeführt und entsprachen der Erwartung.
