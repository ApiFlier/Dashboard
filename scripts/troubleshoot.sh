#!/usr/bin/env bash

# Diagnoses common AirfieldOps problems and offers safe repair options.
# Does not delete volumes, reset data, or expose secrets.

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$SCRIPT_DIR"

APP_PORT=8081
if [ -f .env ]; then
    _port=$(grep "^APP_PORT=" .env | cut -d= -f2)
    [ -n "$_port" ] && APP_PORT=$_port
fi
APP_URL="http://localhost:${APP_PORT}"

PASS=0
WARN=0
FAIL=0

_ok()   { echo "  [✓] $*"; PASS=$((PASS+1)); }
_warn() { echo "  [!] $*"; WARN=$((WARN+1)); }
_fail() { echo "  [✗] $*"; FAIL=$((FAIL+1)); }

echo ""
echo "=============================================="
echo "  AirfieldOps — Diagnostics"
echo "=============================================="
echo ""
echo "  Running checks..."
echo ""

# 1. Docker
if command -v docker &>/dev/null; then
    _ok "Docker found: $(docker --version | head -1)"
else
    _fail "Docker not found. Install Docker Engine first."
    echo ""
    echo "  Nothing else to check without Docker."
    exit 1
fi

# 2. Docker Compose
if docker compose version &>/dev/null; then
    _ok "Docker Compose plugin found"
    COMPOSE="docker compose"
elif docker-compose version &>/dev/null; then
    _ok "docker-compose (legacy) found"
    COMPOSE="docker-compose"
else
    _fail "Docker Compose not found"
fi

# 3. .env
if [ -f .env ]; then
    _ok ".env file found"
else
    _fail ".env not found. Run ./setup.sh or ./menu.sh option 1."
fi

# 4. deploy/docker-compose.prod.yml
if [ -f deploy/docker-compose.prod.yml ]; then
    _ok "deploy/docker-compose.prod.yml found"
    if $COMPOSE -f deploy/docker-compose.prod.yml config --quiet 2>/dev/null; then
        _ok "Compose config is valid"
    else
        _fail "Compose config has errors — check deploy/docker-compose.prod.yml"
    fi
else
    _fail "deploy/docker-compose.prod.yml missing"
fi

# 5. Container status
CONTAINER_STATUS=$(docker inspect --format='{{.State.Status}}' airfieldops-app 2>/dev/null || echo "not_found")
if [ "$CONTAINER_STATUS" = "running" ]; then
    _ok "Container airfieldops-app is running"
elif [ "$CONTAINER_STATUS" = "not_found" ]; then
    _fail "Container airfieldops-app not found. Run ./menu.sh option 1 or 2."
else
    _fail "Container airfieldops-app exists but is: $CONTAINER_STATUS"
fi

# 6. Health endpoint
if curl -sf "${APP_URL}/api/health" >/dev/null 2>&1; then
    _ok "Health endpoint OK: ${APP_URL}/api/health"
else
    _fail "Health endpoint unreachable: ${APP_URL}/api/health"
fi

# 7. Reference data endpoint
REF_RESP=$(curl -sf "${APP_URL}/api/reference/status" 2>/dev/null || echo "")
if echo "$REF_RESP" | grep -q "airport_count"; then
    APT_COUNT=$(echo "$REF_RESP" | python3 -c "import sys,json; print(json.load(sys.stdin).get('airport_count','?'))" 2>/dev/null || echo "?")
    _ok "Reference data: ${APT_COUNT} airports in DB"
else
    _warn "Reference data status endpoint did not respond as expected"
fi

# 8. Recent logs — errors only
echo ""
echo "  --- Recent log summary (last 60 lines) ---"
docker logs airfieldops-app --tail=60 2>&1 | grep -iE "error|exception|traceback|critical|fail" | head -20 || true
echo "  --- End of log summary ---"

echo ""
echo "  =============================================="
echo "  Results: ${PASS} passed  ${WARN} warnings  ${FAIL} failed"
echo "  =============================================="
echo ""

if [ $FAIL -eq 0 ] && [ $WARN -eq 0 ]; then
    echo "  Everything looks good."
    echo ""
    exit 0
fi

# Offer repair options
echo "  Repair options:"
echo ""
echo "  1) Show full recent logs (last 100 lines)"
echo "  2) Restart the app container (safe — no data loss)"
echo "  3) Rebuild and restart the app container"
echo "  4) Return to menu / exit"
echo ""
printf "  Choose an option [1-4]: "
read -r repair_choice < /dev/tty || repair_choice="4"

case "$repair_choice" in
    1)
        echo ""
        docker logs airfieldops-app --tail=100 2>&1 || true
        echo ""
        ;;
    2)
        echo ""
        printf "  Restart airfieldops-app container? [y/N] "
        read -r confirm < /dev/tty || confirm="N"
        if [ "$confirm" = "y" ] || [ "$confirm" = "Y" ]; then
            echo "  Restarting..."
            docker restart airfieldops-app
            echo "  Waiting for health check..."
            RETRIES=0
            until curl -sf "${APP_URL}/api/health" >/dev/null 2>&1; do
                sleep 2
                RETRIES=$((RETRIES+1))
                if [ $RETRIES -ge 20 ]; then
                    echo "  [!] Health check did not pass after restart. Check logs."
                    exit 1
                fi
            done
            echo "  [✓] Container healthy: ${APP_URL}"
        else
            echo "  Restart skipped."
        fi
        ;;
    3)
        echo ""
        printf "  Rebuild and restart? This is safe but takes a minute. [y/N] "
        read -r confirm < /dev/tty || confirm="N"
        if [ "$confirm" = "y" ] || [ "$confirm" = "Y" ]; then
            echo "  Running update.sh (which includes rebuild)..."
            bash update.sh
        else
            echo "  Rebuild skipped."
        fi
        ;;
    *)
        echo "  Run ./menu.sh to return to the main menu."
        ;;
esac
echo ""
