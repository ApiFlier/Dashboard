#!/usr/bin/env bash

set -e

mkdir -p backups
TIMESTAMP=$(date +"%Y%m%d_%H%M%S")
BACKUP_FILE="backups/backup_${TIMESTAMP}.tar.gz"

# Get absolute path for clarity
ABS_BACKUP_PATH=$(readlink -f "$BACKUP_FILE" 2>/dev/null || echo "$(pwd)/$BACKUP_FILE")

echo "Starting backup of AirfieldOps runtime state..."
echo "Destination: $ABS_BACKUP_PATH"

# Create a temporary directory to assemble the backup
TMP_DIR=$(mktemp -d)
cleanup() {
    rm -rf "$TMP_DIR"
}
trap cleanup EXIT

# 1. Backup .env
if [ -f .env ]; then
    cp .env "$TMP_DIR/"
    echo "  [+] .env included"
else
    echo "  [!] .env not found, skipping"
fi

# 2. Backup the docker volume airfieldops_state
if docker volume inspect airfieldops_state &> /dev/null; then
    echo "  [+] Backing up Docker volume 'airfieldops_state'..."
    docker run --rm \
        -v airfieldops_state:/var/lib/airfieldops \
        -v "$TMP_DIR:/backup_dir" \
        alpine tar -czf /backup_dir/airfieldops_state.tar.gz -C /var/lib/airfieldops .
    echo "  [+] Volume backup complete"
else
    echo "  [!] Docker volume 'airfieldops_state' not found, skipping"
fi

# Assemble final tarball
tar -czf "$BACKUP_FILE" -C "$TMP_DIR" .

# Fix permissions if created via root in docker volume backup step
CURRENT_USER=$(id -u):$(id -g)
sudo chown "$CURRENT_USER" "$BACKUP_FILE" 2>/dev/null || true

echo "------------------------------------------------"
echo "Backup successfully created: $ABS_BACKUP_PATH"
echo "Keep this file private; it may include .env and runtime database contents."
echo "------------------------------------------------"
