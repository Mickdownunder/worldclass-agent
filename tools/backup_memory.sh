#!/bin/bash
# /root/operator/tools/backup_memory.sh
# Zips the Operator Memory (SQLite), Plumber data, and June's MEMORY.md

BACKUP_DIR="/root/operator/backups"
mkdir -p "$BACKUP_DIR"

DATE=$(date +%Y-%m-%d)
BACKUP_FILE="$BACKUP_DIR/memory_backup_$DATE.tar.gz"

echo "Creating backup $BACKUP_FILE..."

# Zip the important state files
tar -czf "$BACKUP_FILE" -C / \
    root/operator/memory \
    root/operator/plumber \
    root/agent/workspace/MEMORY.md 2>/dev/null

# Keep only the last 7 backups to save disk space
find "$BACKUP_DIR" -name "memory_backup_*.tar.gz" -type f -mtime +7 -delete

echo "Backup complete: $BACKUP_FILE"

# ---------------------------------------------------------
# OPTIONAL: Remote Sync (Uncomment and configure if needed)
# ---------------------------------------------------------
# rclone copy "$BACKUP_FILE" remote:backup-bucket/operator/
# aws s3 cp "$BACKUP_FILE" s3://my-backup-bucket/operator/
