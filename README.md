# AirfieldOps Core

AirfieldOps Core is a self-hosted, advisory/display-only airport operations dashboard. It is designed for small airports, FBOs, flight schools, and charter operators to provide a unified view of operational data for a selected airport.

## Project Purpose
To provide a consolidated, quick-reference view of airport conditions (weather, runways, alternates, hazards) without needing multiple browser tabs. 

## MVP Scope
- Unified dashboard for a single selected airport.
- Fetch and display METAR/TAF, runway wind conditions, nearby alternates, and regional weather hazards.
- Purely advisory information.

## Explicit Non-Goals
- **No Certified Flight Planning:** This is not for legal dispatch, release, or operational control.
- **No OpenSky:** OpenSky data is intentionally not used in this project.
- **No NOTAMs:** NOTAM parsing and display are out of scope for the MVP. No fake NOTAM placeholders are used.
- **No SWIM Integration:** Future only.

## Data Sources
- AviationWeather.gov API (METAR, TAF, Airport, Station, PIREP, SIGMET, G-AIRMET, CWA)
- NWS API (Alerts, Point Forecasts)

## Disclaimer
**Advisory display only. Not for certified flight planning, dispatch, release, or operational control.**

The runway intelligence and alternate ranking modules are simple advisory helpers. They do not replace pilot judgment, official performance charts, or certified flight planning tools.

## Development vs Production

### Development Workflow
For development, you need the local source code.
```bash
docker compose up --build
```
This uses local folder bind mounts, allowing live-reloading of changes. It is meant exclusively for development.

### Production Workflow
For production, the application is designed to be "stupid-simple" to deploy and run completely decoupled from the source directory.

Run the setup script:
```bash
./setup.sh
```
This script will:
1. Find a free port for the app (default 8080).
2. Provision a persistent Docker named volume (`airfieldops_state`).
3. Build and launch the container with `restart: unless-stopped`.
4. Optionally allow you to delete all local source files (`DELETE SOURCE`).

Once deployed in production, the running container no longer relies on the local source repo. Normal restarts and host reboots are handled by Docker. If you need to upgrade the application later and you deleted the source files, you must re-clone the repository. If you accidentally delete the container, you need `setup.sh` or a recloned repo to recreate it (your Docker volume with state will persist).

To restore from a backup, use `restore.sh`. It safely creates a pre-restore backup and requires typed confirmation before overwriting your runtime state.

### Data Model
- **Reference Data:** Shipped with the app (e.g., airport data). Seeded into the SQLite runtime database on first run.
- **Live Data:** Fetched fresh from APIs. Weather cache is disposable. Source data may be missing, partially unavailable, or stale. The app is designed to degrade gracefully and provide warnings when data is missing.
- **Persistent State:** Config, history, and the SQLite runtime database (`airfieldops.sqlite`) are stored in the persistent Docker volume at `/var/lib/airfieldops`.

## Testing
To run the test suite:
```bash
pytest
```# Dashboard
