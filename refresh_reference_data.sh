#!/usr/bin/env bash

set -e

DRY_RUN=false
if [[ "$1" == "--dry-run" ]]; then
    DRY_RUN=true
    echo "--- DRY RUN MODE ---"
fi

echo "Starting reference data refresh workflow..."

# 1. Verify Docker/Compose
if ! command -v docker &> /dev/null; then
    echo "Error: Docker not found."
    exit 1
fi

if ! docker compose version &> /dev/null; then
    echo "Error: Docker Compose not found."
    exit 1
fi

# 2. Verify App State
if ! docker ps | grep -q airfieldops; then
    echo "Error: airfieldops container is not running."
    exit 1
fi

# 3. Backup before changing anything (unless dry-run)
if [ "$DRY_RUN" = false ]; then
    echo "Creating pre-refresh backup..."
    ./backup.sh
else
    echo "Skipping backup for dry-run."
fi

# 4. Get current counts
if [ -f .env ]; then
    source .env
fi
PORT=${APP_PORT:-8080}

echo "Current reference status (port $PORT):"
curl -s http://localhost:$PORT/api/reference/status | python3 -c "import sys, json; d=json.load(sys.stdin); print(f'Airports: {d[\"airport_count\"]}, Runways: {d[\"runway_count\"]}, Frequencies: {d[\"frequency_count\"]} (Source: {d[\"source\"]})')"

# 5. Run Import
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
REPORT_FILE="reports/reference_import_${TIMESTAMP}.json"
DRY_RUN_ARG=""
if [ "$DRY_RUN" = true ]; then
    DRY_RUN_ARG="--dry-run"
fi

echo "Running import..."
docker compose exec airfieldops python3 scripts/import_ourairports.py --report "$REPORT_FILE" $DRY_RUN_ARG

# 6. Run Validation
echo "Running validation..."
docker compose exec airfieldops python3 scripts/validate_reference_data.py

# 7. Check final status
if [ "$DRY_RUN" = false ]; then
    echo "Final reference status:"
    curl -s http://localhost:$PORT/api/reference/status | python3 -c "import sys, json; d=json.load(sys.stdin); print(f'Airports: {d[\"airport_count\"]}, Runways: {d[\"runway_count\"]}, Frequencies: {d[\"frequency_count\"]} (Source: {d[\"source\"]})')"
    echo "Workflow complete. Report: $REPORT_FILE"
else
    echo "Dry-run complete. No changes made to database."
    echo "Report: $REPORT_FILE"
fi
