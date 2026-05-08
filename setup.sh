#!/usr/bin/env bash

set -e

echo "Starting setup..."

if ! command -v docker &> /dev/null; then
    echo "Error: Docker is not installed."
    exit 1
fi

if ! docker compose version &> /dev/null; then
    if ! docker-compose version &> /dev/null; then
        echo "Error: Docker Compose is not installed."
        exit 1
    else
        DOCKER_COMPOSE_CMD="docker-compose"
    fi
else
    DOCKER_COMPOSE_CMD="docker compose"
fi

if [ ! -f .env ]; then
    echo "Creating .env with production defaults..."
    cat > .env <<'EOF'
APP_NAME="AirfieldOps"
APP_ENV=production
APP_PORT=8080
DEFAULT_AIRPORT=KAGC
CACHE_TTL_SECONDS=300
HTTP_TIMEOUT_SECONDS=10
AIRFIELDOPS_USER_AGENT="AirfieldOps/1.0 (self-hosted)"
PUBLIC_READONLY_MODE=true
ADMIN_API_TOKEN=
DEBUG_PUBLIC_ENDPOINTS=false
AIRFIELDOPS_STATE_DIR=/var/lib/airfieldops
AIRFIELDOPS_DB_PATH=/var/lib/airfieldops/airfieldops.sqlite
EOF
fi

# Load .env so PORT and other vars are available to this script
set -a
source .env
set +a

PORT=${APP_PORT:-8080}
echo "Checking if port $PORT is available..."
# /dev/tcp doesn't always work in all bash versions or environments, using a simple python check or nc if available.
# A small python script is reliable:
while python3 -c "import socket; s = socket.socket(socket.AF_INET, socket.SOCK_STREAM); exit(s.connect_ex(('127.0.0.1', $PORT)) != 0)"; do
    echo "Port $PORT is in use, trying next..."
    PORT=$((PORT+1))
done
echo "Using port $PORT."

# Write the chosen port back to .env
if [ -f .env ]; then
    if grep -q "^APP_PORT=" .env; then
        sed -i.bak "s/^APP_PORT=.*/APP_PORT=$PORT/" .env
        rm -f .env.bak
    else
        echo "APP_PORT=$PORT" >> .env
    fi
fi

# Export it for docker compose below
export APP_PORT=$PORT

mkdir -p backups

echo "Ensuring Docker named volume 'airfieldops_state' exists..."
docker volume create airfieldops_state >/dev/null

# Remove any existing AirfieldOps containers before starting.
# This prevents Docker name conflicts on re-runs and migrates from legacy names.
# Volumes are never touched — only the container process is replaced.
for _cname in airfieldops_prod airfieldops airfieldops-app; do
    if docker ps -a --format '{{.Names}}' | grep -q "^${_cname}$"; then
        echo "Removing existing container '${_cname}' (volume state preserved)..."
        docker stop "${_cname}" 2>/dev/null || true
        docker rm "${_cname}" 2>/dev/null || true
    fi
done

echo "Starting application in production mode..."
$DOCKER_COMPOSE_CMD -f deploy/docker-compose.prod.yml up --build -d

echo "Waiting for application to become healthy on port $PORT..."
RETRIES=0
MAX_RETRIES=30
while ! curl -s -f http://localhost:$PORT/api/health > /dev/null; do
    sleep 2
    RETRIES=$((RETRIES+1))
    if [ $RETRIES -ge $MAX_RETRIES ]; then
        echo "Error: Application health check failed."
        exit 1
    fi
done

echo "Application is up and running!"
echo "Access the dashboard at: http://localhost:$PORT"

echo ""
echo "Delete local source files now? [y/N]"
echo "(The running app and all Docker volume state are preserved either way.)"
read -r user_input
case "${user_input}" in
    [yY])
        echo "Removing source files..."
        find . -mindepth 1 -maxdepth 1 \
            ! -name '.env' \
            ! -name 'backups' \
            ! -name 'backup.sh' \
            ! -name 'restore.sh' \
            ! -name 'setup.sh' \
            -exec rm -rf {} +
        echo "Source files removed. The app continues running via Docker."
        ;;
    *)
        echo "Source files preserved."
        ;;
esac

echo "Setup complete."
