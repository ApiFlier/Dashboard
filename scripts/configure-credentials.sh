#!/usr/bin/env bash

# Updates user-editable config in .env.
# Never prints secret values. Shows [set] / [not set] only.

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$SCRIPT_DIR"

ENV_FILE=".env"

echo ""
echo "=========================================="
echo "  AirfieldOps — Configure / Update Config"
echo "=========================================="
echo ""
echo "  Press Enter to keep the current value."
echo "  Type a new value and press Enter to change it."
echo "  Secret values are never displayed."
echo ""

if [ ! -f "$ENV_FILE" ]; then
    echo "  [!] .env not found. Run ./setup.sh first."
    exit 1
fi

# Helper: get current value from .env without printing it
_get_val() {
    grep "^${1}=" "$ENV_FILE" 2>/dev/null | cut -d= -f2- | sed "s/^['\"]//;s/['\"]$//"
}

# Helper: set or update a key in .env
_set_val() {
    local key="$1" val="$2"
    if grep -q "^${key}=" "$ENV_FILE"; then
        sed -i "s|^${key}=.*|${key}=${val}|" "$ENV_FILE"
    else
        echo "${key}=${val}" >> "$ENV_FILE"
    fi
}

# Helper: show [set] / [not set] status
_show_status() {
    local key="$1"
    local val
    val=$(_get_val "$key")
    if [ -n "$val" ]; then
        echo "  ${key} : [set]"
    else
        echo "  ${key} : [not set]"
    fi
}

echo "  Current config status (no secret values shown):"
_show_status "DEFAULT_AIRPORT"
_show_status "ADMIN_API_TOKEN"
_show_status "AIRFIELDOPS_USER_AGENT"
_show_status "PUBLIC_READONLY_MODE"
_show_status "APP_PORT"
echo ""

# --- DEFAULT_AIRPORT ---
cur=$(_get_val "DEFAULT_AIRPORT")
printf "  DEFAULT_AIRPORT (currently: %s): " "${cur:-not set}"
read -r new_val < /dev/tty
if [ -n "$new_val" ]; then
    _set_val "DEFAULT_AIRPORT" "$new_val"
    echo "  → DEFAULT_AIRPORT updated."
fi

# --- ADMIN_API_TOKEN ---
cur_status="not set"
cur=$(_get_val "ADMIN_API_TOKEN")
[ -n "$cur" ] && cur_status="[set — not shown]"
printf "  ADMIN_API_TOKEN (currently: %s): " "$cur_status"
read -r new_val < /dev/tty
if [ -n "$new_val" ]; then
    _set_val "ADMIN_API_TOKEN" "$new_val"
    echo "  → ADMIN_API_TOKEN updated."
elif [ -z "$cur" ]; then
    echo "  → Kept empty. Mutation endpoints will remain blocked."
fi

# --- AIRFIELDOPS_USER_AGENT ---
cur=$(_get_val "AIRFIELDOPS_USER_AGENT")
printf "  AIRFIELDOPS_USER_AGENT (currently: %s): " "${cur:-not set}"
read -r new_val < /dev/tty
if [ -n "$new_val" ]; then
    _set_val "AIRFIELDOPS_USER_AGENT" "\"$new_val\""
    echo "  → AIRFIELDOPS_USER_AGENT updated."
fi

# --- PUBLIC_READONLY_MODE ---
cur=$(_get_val "PUBLIC_READONLY_MODE")
printf "  PUBLIC_READONLY_MODE [true/false] (currently: %s): " "${cur:-true}"
read -r new_val < /dev/tty
if [ "$new_val" = "true" ] || [ "$new_val" = "false" ]; then
    _set_val "PUBLIC_READONLY_MODE" "$new_val"
    echo "  → PUBLIC_READONLY_MODE updated."
elif [ -n "$new_val" ]; then
    echo "  → Invalid value (must be true or false). Kept as-is."
fi

echo ""
echo "  Config updated."
echo ""
printf "  Restart the container to apply changes? [y/N] "
read -r restart_choice < /dev/tty
if [ "$restart_choice" = "y" ] || [ "$restart_choice" = "Y" ]; then
    echo "  Restarting container..."
    DOCKER_COMPOSE_CMD="docker compose"
    docker compose version &>/dev/null || DOCKER_COMPOSE_CMD="docker-compose"
    $DOCKER_COMPOSE_CMD -f deploy/docker-compose.prod.yml up -d
    echo "  Done. Run ./menu.sh option 4 to verify."
else
    echo "  Container not restarted. Changes will apply on next restart."
    echo "  Run ./menu.sh → option 2 (update) or option 5 (troubleshoot) when ready."
fi
echo ""
