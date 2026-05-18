#!/usr/bin/env bash

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# Load port from .env without printing it
APP_PORT=8081
if [ -f .env ]; then
    _port=$(grep "^APP_PORT=" .env | cut -d= -f2)
    [ -n "$_port" ] && APP_PORT=$_port
fi
APP_URL="http://localhost:${APP_PORT}"

print_banner() {
    echo ""
    echo "╔══════════════════════════════════════════════════════╗"
    echo "║           AirfieldOps  —  Operations Menu            ║"
    echo "║   Aviation situational awareness · Advisory only     ║"
    echo "╚══════════════════════════════════════════════════════╝"
    echo ""
}

print_status() {
    # Docker availability
    if ! command -v docker &>/dev/null; then
        echo "  [!] Docker   : NOT FOUND — install Docker first"
        return
    fi
    echo "  [✓] Docker   : available"

    # Container status
    local status
    status=$(docker inspect --format='{{.State.Status}}' airfieldops-app 2>/dev/null || echo "not found")
    if [ "$status" = "running" ]; then
        echo "  [✓] Container: running"
    elif [ "$status" = "not found" ]; then
        echo "  [!] Container: not running — run option 1 to set up"
    else
        echo "  [!] Container: $status"
    fi

    # Health check
    if curl -sf "${APP_URL}/api/health" >/dev/null 2>&1; then
        echo "  [✓] App URL  : ${APP_URL}"
    else
        echo "  [!] App URL  : ${APP_URL}  (health check failed or container not running)"
    fi

    # Config summary (no secret values)
    if [ -f .env ]; then
        local readonly_mode admin_token_status
        readonly_mode=$(grep "^PUBLIC_READONLY_MODE=" .env | cut -d= -f2)
        admin_token_raw=$(grep "^ADMIN_API_TOKEN=" .env | cut -d= -f2)
        if [ -n "$admin_token_raw" ]; then
            admin_token_status="[set]"
        else
            admin_token_status="[not set — mutations blocked]"
        fi
        echo "  [i] Read-only mode : ${readonly_mode:-true}"
        echo "  [i] Admin token    : ${admin_token_status}"
    else
        echo "  [!] .env     : missing — run option 1 to set up"
    fi
    echo ""
}

while true; do
    clear
    print_banner
    print_status

    echo "  1) Set up the app for the first time"
    echo "  2) Update the app"
    echo "  3) Update config / credentials"
    echo "  4) Check app status and open URL"
    echo "  5) Troubleshoot / repair"
    echo "  6) Advanced tools"
    echo "  7) Quit"
    echo ""
    printf "  Choose an option [1-7]: "
    read -r choice

    case "$choice" in
        1)
            echo ""
            echo "Running setup.sh ..."
            echo ""
            bash setup.sh
            echo ""
            printf "Press Enter to return to menu..."
            read -r
            ;;
        2)
            echo ""
            echo "Running update.sh ..."
            echo ""
            bash update.sh
            echo ""
            printf "Press Enter to return to menu..."
            read -r
            ;;
        3)
            echo ""
            if [ -f scripts/configure-credentials.sh ]; then
                bash scripts/configure-credentials.sh
            else
                echo "  Edit .env directly to update config keys."
                echo "  Never share or print secret values."
                echo ""
                echo "  Keys you can safely change:"
                echo "    DEFAULT_AIRPORT          — ICAO code shown on load"
                echo "    ADMIN_API_TOKEN          — token for mutation endpoints (leave blank to block all mutations)"
                echo "    AIRFIELDOPS_USER_AGENT   — identifies your instance to upstream APIs"
                echo "    PUBLIC_READONLY_MODE     — true/false"
                echo "    APP_PORT                 — host port (requires container restart)"
            fi
            echo ""
            printf "Press Enter to return to menu..."
            read -r
            ;;
        4)
            echo ""
            print_status
            echo "  Dashboard : ${APP_URL}/"
            echo "  Ops Mode  : ${APP_URL}/#/ops"
            echo "  Health    : ${APP_URL}/api/health"
            echo ""
            printf "Press Enter to return to menu..."
            read -r
            ;;
        5)
            echo ""
            if [ -f scripts/troubleshoot.sh ]; then
                bash scripts/troubleshoot.sh
            else
                echo "  scripts/troubleshoot.sh not found."
                echo ""
                echo "  Quick checks:"
                echo "    docker ps                              — are containers running?"
                echo "    docker compose -f deploy/docker-compose.prod.yml logs --tail=50 airfieldops"
                echo "    curl ${APP_URL}/api/health"
            fi
            echo ""
            printf "Press Enter to return to menu..."
            read -r
            ;;
        6)
            echo ""
            echo "  Advanced tools:"
            echo "    ./backup.sh                          — backup runtime state"
            echo "    ./restore.sh <file>                  — restore from backup"
            echo "    ./refresh_reference_data.sh          — refresh airport DB from OurAirports"
            echo "    ./refresh_reference_data.sh --dry-run — preview refresh"
            echo "    docker compose -f deploy/docker-compose.prod.yml logs --tail=100 airfieldops"
            echo "    docker exec -it airfieldops-app bash  — shell into running container"
            echo ""
            printf "Press Enter to return to menu..."
            read -r
            ;;
        7|q|Q)
            echo ""
            echo "  Goodbye."
            echo ""
            exit 0
            ;;
        *)
            echo ""
            echo "  Invalid option. Please enter 1-7."
            sleep 1
            ;;
    esac
done
