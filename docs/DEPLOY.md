# Operator live auf den Server bringen

Du hast bisher nur mit `npm run dev` gearbeitet. So baust du das System für den **Produktionsbetrieb** auf dem Server auf.

---

## 1. Voraussetzungen auf dem Server

- **Node.js 20+** (für Next.js UI)
- **Python 3.11+** und **pnpm** oder **npm** (je nachdem, was du nutzt)
- Operator-Code liegt z. B. unter `/root/operator` (oder dein gewünschter Pfad = `OPERATOR_ROOT`)

Auf dem Server muss der **gesamte Operator** liegen (nicht nur die UI): also `bin/`, `tools/`, `workflows/`, `research/`, `conf/`, `memory/`, etc. Die UI führt Befehle wie `bin/op`, `bin/brain` und Python-Tools aus – alle relativ zu `OPERATOR_ROOT`.

---

## 2. Code auf den Server

Beispiel mit Git (auf dem Server):

```bash
# Falls noch nicht vorhanden
git clone <dein-repo> /root/operator
cd /root/operator
```

Oder von deiner Maschine per rsync (ohne node_modules):

```bash
rsync -av --exclude=node_modules --exclude=ui/node_modules --exclude=.next ./ root@DEIN-SERVER:/root/operator/
```

---

## 3. Umgebung setzen

Die UI braucht zur Laufzeit:

| Variable | Pflicht | Beschreibung |
|----------|--------|--------------|
| `OPERATOR_ROOT` | Nein (Default: `/root/operator`) | Absoluter Pfad zum Operator-Verzeichnis auf dem Server. |
| `UI_PASSWORD_HASH` | Ja (für Login) | SHA-256-Hash des Passworts in Hex: `echo -n "deinpasswort" \| sha256sum \| cut -d' ' -f1` |
| `UI_SESSION_SECRET` | Ja (für Sessions) | Zufälliger String, z. B. `openssl rand -hex 32` |
| `PORT` | Nein (Default: 3000) | Port, auf dem die UI laufen soll. |

**Option A: `.env.local` im UI-Ordner (einfach für manuellen Start)**

```bash
cd /root/operator/ui
cp .env.local.example .env.local
# Dann .env.local bearbeiten:
# OPERATOR_ROOT=/root/operator
# UI_PASSWORD_HASH=<output von sha256sum>
# UI_SESSION_SECRET=<output von openssl rand -hex 32>
```

**Option B: Export vor dem Start (für systemd/Shell)**

```bash
export OPERATOR_ROOT=/root/operator
export UI_PASSWORD_HASH="..."
export UI_SESSION_SECRET="..."
export PORT=3000
```

---

## 4. UI bauen und starten

**Variante A: Manuell**

```bash
cd /root/operator/ui

# Dependencies (einmalig bzw. nach package.json-Änderungen)
npm ci

# Production-Build (einmalig bzw. nach Code-Änderungen)
npm run build

# Server starten (bleibt im Vordergrund; zum Dauerbetrieb siehe Abschnitt 5)
npm run start
```

**Variante B: Skript (aus Operator-Root)**

```bash
cd /root/operator
# Env in .env.local setzen (ui/.env.local) oder exportieren
OPERATOR_ROOT=/root/operator ./scripts/run-ui-production.sh
```

Das Skript baut bei Bedarf einmalig und startet dann `npm run start`. Nur bauen: `./scripts/run-ui-production.sh --build-only`.

Die UI läuft dann auf `http://<server>:3000` (oder dem gewählten `PORT`).  
**Wichtig:** `OPERATOR_ROOT` muss auf dem Server auf das Verzeichnis zeigen, in dem `bin/op`, `tools/`, etc. liegen. Die UI führt dort `op`, `brain` und Python-Skripte aus.

---

## 5. Dauerhaft laufen lassen (systemd)

Damit die UI nach Neustart oder Abbruch wieder startet:

1. **Unit-Datei anlegen** – Vorlage aus dem Repo kopieren und anpassen:
   ```bash
   sudo cp /root/operator/scripts/operator-ui.service.example /etc/systemd/system/operator-ui.service
   sudo nano /etc/systemd/system/operator-ui.service   # UI_PASSWORD_HASH, UI_SESSION_SECRET, ggf. Pfad setzen
   ```
   Oder manuell (z. B. `/etc/systemd/system/operator-ui.service`):

```ini
[Unit]
Description=Operator Next.js UI
After=network.target

[Service]
Type=simple
User=root
WorkingDirectory=/root/operator/ui
Environment=OPERATOR_ROOT=/root/operator
Environment=UI_PASSWORD_HASH=DEIN_HASH_HIER
Environment=UI_SESSION_SECRET=DEIN_SECRET_HIER
Environment=PORT=3000
ExecStart=/usr/bin/npm run start
Restart=on-failure
RestartSec=5

[Install]
WantedBy=multi-user.target
```

2. **Aktivieren und starten:**

```bash
sudo systemctl daemon-reload
sudo systemctl enable operator-ui
sudo systemctl start operator-ui
sudo systemctl status operator-ui
```

Logs: `journalctl -u operator-ui -f`

---

## 6. Optional: Reverse-Proxy (nginx) und HTTPS

Wenn die UI von außen erreichbar sein soll (z. B. mit HTTPS), stellst du einen Reverse-Proxy vor die App:

- **nginx:** Proxy auf `http://127.0.0.1:3000`, SSL mit z. B. Let’s Encrypt.
- **Caddy:** Automatisches HTTPS, Proxy auf `localhost:3000`.

Die Next.js-App läuft weiter auf Port 3000; nginx/Caddy lauscht auf 80/443 und leitet dorthin weiter.

---

## 7. Kurz-Checkliste

1. Operator-Code auf dem Server unter `OPERATOR_ROOT`.
2. `OPERATOR_ROOT`, `UI_PASSWORD_HASH`, `UI_SESSION_SECRET` setzen (`.env.local` oder systemd/Export).
3. `cd $OPERATOR_ROOT/ui && npm ci && npm run build && npm run start` (oder systemd).
4. Im Browser: `http://<server>:3000` – Login mit dem Passwort, dessen Hash du gesetzt hast.
5. Research/Jobs/Brain laufen über die gleiche Instanz; alle API-Routen nutzen `OPERATOR_ROOT` auf dem Server.

Damit hast du das System **live** auf dem Server – nicht mehr nur `npm run dev`, sondern Production-Build und stabiler Betrieb.
