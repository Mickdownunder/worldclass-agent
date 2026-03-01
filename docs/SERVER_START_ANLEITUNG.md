# So startest du das Ding auf dem Server

Einfache Schritte – du brauchst Zugriff auf den Server (SSH oder Konsole).

---

## Voraussetzung

- Auf dem Server: **Node.js** (Version 20 oder neuer), **Python 3** und **Docker** sind installiert und laufen.
- Du hast den **kompletten Operator-Ordner** auf dem Server (z.B. per Git, rsync oder ZIP). Der Ordner soll z.B. unter `/root/operator` liegen – das ist dein „Operator-Root“.

**Warum Docker?** Die Research-Sandbox (Trial-&-Error-Code der KI) läuft in einem Docker-Container (`python:3.11-slim`). Ohne Docker funktioniert der Rest der App, aber die Experiment-Phase („Sandbox / Sub-agents“) kann dann keinen Code ausführen. Docker prüfen: `docker info`

---

## Schritt 1: Zum Operator-Ordner wechseln

Auf dem Server in der Konsole:

```bash
cd /root/operator
```

(Wenn dein Ordner woanders liegt, ersetze `/root/operator` durch deinen Pfad.)

---

## Schritt 2: Umgebung prüfen / setzen

Die UI braucht drei Dinge. Die kannst du in der Datei `ui/.env.local` eintragen.

**Datei anlegen oder anpassen:**

```bash
nano ui/.env.local
```

Dort mindestens diese Zeilen (Werte anpassen):

```text
OPERATOR_ROOT=/root/operator
UI_PASSWORD_HASH=HIER_DEN_PASSWORT_HASH
UI_SESSION_SECRET=HIER_EIN_LANGER_ZUFALLSSTRING
```

**Passwort-Hash erzeugen** (auf deinem Rechner oder dem Server):

```bash
echo -n "DEIN_LOGIN_PASSWORT" | sha256sum | cut -d' ' -f1
```

Die ausgegebene Zeile (langer Hex-String) ist dein `UI_PASSWORD_HASH`.

**Session-Secret erzeugen:**

```bash
openssl rand -hex 32
```

Die Ausgabe ist dein `UI_SESSION_SECRET`.

Speichern in nano: Strg+O, Enter, dann Strg+X.

---

## Schritt 3: UI bauen

```bash
cd /root/operator/ui
npm install
npm run build
```

Warten, bis „Build done“ o.ä. erscheint (kann ein paar Minuten dauern).

---

## Schritt 4: UI starten

```bash
npm run start
```

Die App läuft dann auf **Port 3000**. Im Browser:

**http://DEINE-SERVER-IP:3000**

(z.B. http://192.168.1.100:3000 oder http://mein-server.de:3000)

Login: Das Passwort, von dem du oben den Hash erzeugt hast.

---

## Schritt 5: Dauerhaft laufen lassen (optional)

Wenn du die Konsole schließt, stoppt die App. Damit sie weiterläuft, kannst du z.B.:

- **screen** nutzen:  
  `screen -S operator`  
  dann Schritt 4 ausführen, mit Strg+A, D abkoppeln. Später wieder verbinden mit: `screen -r operator`

Oder einen Dienst einrichten (z.B. systemd) – siehe `docs/DEPLOY.md`.

---

## Kurz-Checkliste

1. `cd /root/operator`
2. `ui/.env.local` mit OPERATOR_ROOT, UI_PASSWORD_HASH, UI_SESSION_SECRET füllen
3. `cd ui && npm install && npm run build && npm run start`
4. Im Browser: http://SERVER:3000 – mit deinem Passwort einloggen

Wenn etwas nicht klappt: Welche Zeile hast du eingegeben, und was steht in der Fehlermeldung? Das reicht, um gezielt zu helfen.
