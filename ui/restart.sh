#!/bin/bash
cd "$(dirname "$0")"

echo "1. Beende alte Next.js Prozesse..."
pkill -f next-server || true
pkill -f "next start" || true

echo "2. Lösche Next.js Cache..."
rm -rf .next

echo "3. Baue die UI neu..."
npm run build

echo "4. Starte den Server im Hintergrund (0.0.0.0:3000)..."
nohup npm run start -- -p 3000 -H 0.0.0.0 > ui.log 2>&1 < /dev/null &

echo "5. Server startet! Logs können mit 'tail -f ui.log' eingesehen werden."
