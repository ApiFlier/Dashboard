#!/usr/bin/env bash

set -e

BACKUP_FILE="$1"

if [ -z "$BACKUP_FILE" ]; then
    echo "Usage: $0 path/to/backup.tar.gz"
    exit 1
fi

if [ ! -f "$BACKUP_FILE" ]; then
    echo "Error: Backup file not found: $BACKUP_FILE"
    exit 1
fi

# 1. Pre-restore backup
echo "Taking a pre-restore backup of the current state..."
if [ -x ./backup.sh ]; then
    ./backup.sh
else
    echo "Warning: backup.sh not found or not executable. Pre-restore backup skipped."
fi

TMP_DIR=$(mktemp -d)
echo "Extracting backup to temporary directory..."
tar -xzf "$BACKUP_FILE" -C "$TMP_DIR"

# 2. .env handling
if [ -f "$TMP_DIR/.env" ]; then
    if [ -f .env ]; then
        echo ""
        echo "Warning: A local .env file already exists."
        echo "Do you want to overwrite it with the one from the backup? (y/N)"
        read -r confirm_env
        if [[ "$confirm_env" =~ ^[Yy]$ ]]; then
            cp "$TMP_DIR/.env" .env
            echo "  [+] .env restored from backup"
        else
            echo "  [ ] Keeping existing .env"
        fi
    else
        cp "$TMP_DIR/.env" .env
        echo "  [+] .env restored from backup"
    fi
fi

# 3. Volume restoration with strict confirmation
if [ -f "$TMP_DIR/airfieldops_state.tar.gz" ]; then
    echo ""
    echo "CRITICAL: You are about to restore the 'airfieldops_state' Docker volume."
    echo "This will OVERWRITE all current runtime data (SQLite DB, etc.)."
    echo ""
    echo "To proceed, type exactly: RESTORE AIRFIELDOPS"
    read -r confirm_restore

    if [ "$confirm_restore" != "RESTORE AIRFIELDOPS" ]; then
        echo "Restore ABORTED. No changes were made to the Docker volume."
        rm -rf "$TMP_DIR"
        exit 1
    fi

    echo "Stopping container if running..."
    docker stop airfieldops 2>/dev/null || true

    echo "Restoring Docker volume contents..."
    # Ensure volume exists
    docker volume create airfieldops_state >/dev/null
    
    # Clear and extract
    docker run --rm \
        -v airfieldops_state:/var/lib/airfieldops \
        -v "$TMP_DIR:/backup_dir" \
        alpine sh -c "rm -rf /var/lib/airfieldops/* && tar -xzf /backup_dir/airfieldops_state.tar.gz -C /var/lib/airfieldops"
    
    echo "  [+] Volume 'airfieldops_state' restored successfully"
    echo ""
    echo "You must restart the application to use the restored state."
fi

rm -rf "$TMP_DIR"
echo "Restore process finished."
