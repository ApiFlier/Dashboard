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
    echo "Creating .env from .env.example..."
    cp .env.example .env
fi

# Attempt to source .env to load variables if it exists
if [ -f .env ]; then
    set -a
    source .env
    set +a
fi

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

# Check for legacy container name
if docker ps -a --format '{{.Names}}' | grep -q "^airfieldops_prod$"; then
    echo "Warning: A legacy container 'airfieldops_prod' was detected."
    echo "The project now uses 'airfieldops' as the canonical name."
    echo "Do you want to stop and remove the legacy 'airfieldops_prod' container? (y/n)"
    read -r remove_legacy
    if [ "$remove_legacy" = "y" ]; then
        echo "Removing legacy container..."
        docker stop airfieldops_prod || true
        docker rm airfieldops_prod || true
    fi
fi

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
echo "Do you want to remove local source files (leaving only runtime configs and backups)?"
echo "Type exactly 'DELETE SOURCE' to proceed, or anything else to skip:"
read -r user_input

if [ "$user_input" = "DELETE SOURCE" ]; then
    echo "Removing source files..."
    find . -mindepth 1 -maxdepth 1 \
        ! -name '.env' \
        ! -name 'backups' \
        ! -name 'backup.sh' \
        ! -name 'restore.sh' \
        ! -name 'setup.sh' \
        -exec rm -rf {} +
    echo "Source files removed. The application continues running via Docker."
else
    echo "Source files preserved."
fi

echo "Setup complete."
