#!/usr/bin/env bash

set -e

echo "Starting AirfieldOps update process..."

# 1. Verify environment
if ! command -v docker &> /dev/null; then
    echo "Error: Docker is not installed."
    exit 1
fi

if [ ! -f .env ]; then
    echo "Error: .env file missing. Run setup.sh first."
    exit 1
fi

# Load variables
set -a
source .env
set +a

PORT=${APP_PORT:-8080}

# 2. Validate reference data
echo "Validating reference data..."
if [ -f scripts/validate_reference_data.py ]; then
    python3 scripts/validate_reference_data.py
else
    echo "Warning: scripts/validate_reference_data.py not found. Skipping validation."
fi

# 3. Pre-update backup
echo "Creating pre-update backup..."
if [ -x ./backup.sh ]; then
    ./backup.sh
else
    echo "Error: backup.sh not found or not executable. Update aborted for safety."
    exit 1
fi

# 4. Rebuild and restart
echo "Stopping old container if it exists..."
docker stop airfieldops-app 2>/dev/null || true
docker rm airfieldops-app 2>/dev/null || true

echo "Rebuilding and restarting application in production mode..."
if docker compose version &> /dev/null; then
    DOCKER_COMPOSE_CMD="docker compose"
else
    DOCKER_COMPOSE_CMD="docker-compose"
fi

$DOCKER_COMPOSE_CMD -f deploy/docker-compose.prod.yml up --build -d

# 5. Health check
echo "Waiting for application to become healthy on port $PORT..."
RETRIES=0
MAX_RETRIES=30
while ! curl -s -f http://localhost:$PORT/api/health > /dev/null; do
    sleep 2
    RETRIES=$((RETRIES+1))
    if [ $RETRIES -ge $MAX_RETRIES ]; then
        echo "Error: Application health check failed after update."
        exit 1
    fi
done

# 6. Check reference status
echo "Checking reference data status..."
curl -s http://localhost:$PORT/api/reference/status | grep -q "airport_count" || { echo "Warning: Could not verify reference status."; }

echo "------------------------------------------------"
echo "Update complete! Application is running at:"
echo "http://localhost:$PORT"
echo "------------------------------------------------"
