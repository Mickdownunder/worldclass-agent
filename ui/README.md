# Worldclass Agent — Operator UI

Next.js dashboard for the Operator (Tron oldschool style). Requires Operator at `OPERATOR_ROOT` (default `/root/operator`).

## Run

- `npm run dev` — development (port 3000)
- `npm run build` && `npm run start` — production

## Env (.env.local)

- `OPERATOR_ROOT` — path to operator (default `/root/operator`)
- `UI_PASSWORD_HASH` — hex SHA-256 of login password (e.g. `echo -n "mypass" | sha256sum | cut -d' ' -f1`)
- `UI_SESSION_SECRET` — random string for session signing
- `UI_TELEGRAM_NOTIFY=1` — optional: send Telegram when UI triggers factory/brain/retry

## Features

- Login (single user, password)
- Command Center: health, recent activity, Run Factory / Brain Cycle
- Jobs: list, detail, retry
- Packs: list, detail
- Brain & Memory: episodes, reflections, playbooks
- Clients: config list
- Actions logged to `operator/logs/ui-audit.log`
