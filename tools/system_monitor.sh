#!/bin/bash
# /root/operator/tools/system_monitor.sh
# Checks system load and disk space, sends Telegram alert if thresholds are exceeded.

# 1. Check Load (1 min average)
LOAD=$(awk '{print $1}' /proc/loadavg)
LOAD_THRESHOLD=4.0

# 2. Check Disk Space (%)
DISK=$(df / | tail -1 | awk '{print $5}' | sed 's/%//')
DISK_THRESHOLD=90

ALERT_MSG=""

# Bash string to float comparison
if $(echo "$LOAD > $LOAD_THRESHOLD" | bc -l 2>/dev/null || awk -v l="$LOAD" -v t="$LOAD_THRESHOLD" 'BEGIN { if (l > t) exit 0; else exit 1 }'); then
    ALERT_MSG="🚨 *High Server Load*\nLoad Average (1m): $LOAD\n"
fi

if [ "$DISK" -gt "$DISK_THRESHOLD" ]; then
    ALERT_MSG="${ALERT_MSG}🚨 *Disk Space Low*\nRoot partition is at ${DISK}%\n"
fi

# Check for stuck brain processes via plumber's exit code or just basic op health
# (Optional expansion in the future)

if [ -n "$ALERT_MSG" ]; then
    # Format message for Telegram Markdown
    MSG=$(echo -e "$ALERT_MSG")
    /root/operator/tools/send-telegram.sh "$MSG"
fi
