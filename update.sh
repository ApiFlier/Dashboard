#!/usr/bin/env bash

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

echo ""
echo "Starting AirfieldOps update..."
echo ""

# 1. Verify environment
if ! command -v docker &>/dev/null; then
    echo "Error: Docker is not installed."
    exit 1
fi

if docker compose version &>/dev/null; then
    DOCKER_COMPOSE_CMD="docker compose"
elif docker-compose version &>/dev/null; then
    DOCKER_COMPOSE_CMD="docker-compose"
else
    echo "Error: Docker Compose not found."
    exit 1
fi

if [ ! -f .env ]; then
    echo "Error: .env file not found. Run ./menu.sh option 1 (setup) first."
    exit 1
fi

set -a
source .env
set +a
PORT=${APP_PORT:-8080}
echo "Using configured URL: http://localhost:${PORT}"
echo "Runtime data volume 'airfieldops_state' will be preserved."

# 2. Dirty git check
if git rev-parse --is-inside-work-tree &>/dev/null; then
    if ! git diff --quiet || ! git diff --cached --quiet; then
        echo "Warning: You have uncommitted local changes."
        echo ""
        git status --short
        echo ""
        printf "Continue anyway? (git pull may create merge conflicts) [y/N] "
        read -r dirty_choice < /dev/tty || dirty_choice="N"
        if [ "$dirty_choice" != "y" ] && [ "$dirty_choice" != "Y" ]; then
            echo "Update aborted. Commit or stash your changes first."
            exit 1
        fi
    fi

    # 3. Git pull (fast-forward only)
    echo "Pulling latest code (fast-forward only)..."
    if ! git pull --ff-only 2>&1; then
        echo ""
        echo "Error: git pull --ff-only failed."
        echo "Your branch has diverged from the remote. Resolve manually:"
        echo "  git status / git log / git fetch"
        echo "Then rerun ./update.sh or ./menu.sh option 2."
        exit 1
    fi
    echo "Code up to date."
else
    echo "(Not inside a git repo — skipping git pull)"
fi

# 4. Validate reference data
echo ""
echo "Validating reference data..."
if [ -f scripts/validate_reference_data.py ]; then
    python3 scripts/validate_reference_data.py
else
    echo "Warning: scripts/validate_reference_data.py not found. Skipping validation."
fi

# 5. Pre-update backup
echo ""
echo "Creating pre-update backup..."
if [ -x ./backup.sh ]; then
    ./backup.sh
else
    echo "Error: backup.sh not found or not executable. Update aborted for safety."
    exit 1
fi

# 6. Rebuild and restart
echo ""
echo "Stopping old container..."
docker stop airfieldops-app 2>/dev/null || true
docker rm airfieldops-app 2>/dev/null || true

echo "Rebuilding and restarting in production mode..."
$DOCKER_COMPOSE_CMD -f deploy/docker-compose.prod.yml up --build -d

# 7. Health check with logs on failure
echo ""
echo "Waiting for app to become healthy on port ${PORT}..."
RETRIES=0
MAX_RETRIES=30
until curl -sf "http://localhost:${PORT}/api/health" >/dev/null 2>&1; do
    sleep 2
    RETRIES=$((RETRIES+1))
    if [ $RETRIES -ge $MAX_RETRIES ]; then
        echo ""
        echo "Error: Health check failed after update. Recent logs:"
        echo "-------------------------------------------------------"
        docker logs airfieldops-app --tail=50 2>&1 || true
        echo "-------------------------------------------------------"
        echo ""
        echo "Troubleshoot via ./menu.sh option 5, or check logs with:"
        echo "  docker logs airfieldops-app --tail=100"
        exit 1
    fi
done

# 8. Reference status check
echo "Checking reference data..."
curl -sf "http://localhost:${PORT}/api/reference/status" | grep -q "airport_count" \
    || echo "Warning: Could not verify reference status."

echo ""
echo "================================================"
echo "  Update complete!"
echo "  Dashboard : http://localhost:${PORT}/"
echo "  Ops Mode  : http://localhost:${PORT}/#/ops"
echo "  Data      : preserved in Docker volume airfieldops_state"
echo "================================================"
echo ""
echo "  To update config or credentials : ./menu.sh → option 3"
echo "  To troubleshoot                 : ./menu.sh → option 5"
echo ""
