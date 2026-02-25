#!/usr/bin/env bash
set -euo pipefail

# Send a message via Telegram through OpenClaw.
#
# Usage:
#   send-telegram.sh <message_file> [chat_id]
#   send-telegram.sh  (legacy: finds latest telegram.txt)
#
# Env: TELEGRAM_TARGET overrides chat_id argument.

OPENCLAW="/usr/bin/openclaw"

if [[ ! -x "$OPENCLAW" ]]; then
  echo "ERROR: openclaw binary not found at $OPENCLAW" >&2
  exit 1
fi

MSG_FILE=""
TARGET="${TELEGRAM_TARGET:-6615084677}"

if [[ -n "${1:-}" ]] && [[ -f "${1:-}" ]]; then
  MSG_FILE="$1"
  TARGET="${2:-$TARGET}"
elif [[ -n "${1:-}" ]]; then
  TARGET="$1"
fi

if [[ -z "$MSG_FILE" ]]; then
  MSG_FILE=$(find /root/operator/jobs -name telegram.txt -printf "%T@ %p\n" 2>/dev/null | sort -n | tail -n 1 | cut -d' ' -f2- || true)
fi

if [[ -z "$MSG_FILE" ]] || [[ ! -f "$MSG_FILE" ]]; then
  echo "No message file found" >&2
  exit 0
fi

MESSAGE=$(cat "$MSG_FILE")
if [[ -z "$MESSAGE" ]]; then
  echo "Empty message, skipping" >&2
  exit 0
fi

# Truncate to Telegram's 4096 char limit
if [[ ${#MESSAGE} -gt 4000 ]]; then
  MESSAGE="${MESSAGE:0:3950}

... (truncated)"
fi

echo "Sending to $TARGET (${#MESSAGE} chars)..." >&2
"$OPENCLAW" message send --channel telegram --target "$TARGET" --message "$MESSAGE" >/dev/null 2>&1

echo "SENT → $TARGET"
