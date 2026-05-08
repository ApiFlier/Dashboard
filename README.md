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
- **Reference Data:**
  - **Curated Seed:** Hand-verified data for core airports (e.g., KAVP, KAGC) including precise runway threshold coordinates for accurate layouts.
  - **Bulk Import:** Public-domain community data from [OurAirports](https://ourairports.com/data/). Provides broad coverage for thousands of airports, runways, and frequencies.
- **Data Integrity:** Seeded into the SQLite runtime database on first run. Bulk imports can be triggered manually. Curated data is preserved during imports unless superior geometry is found.
- **Live Data:** Fetched fresh from APIs. Weather cache is disposable. Source data may be missing, partially unavailable, or stale. The app is designed to degrade gracefully and provide warnings when data is missing.
- **Persistent State:** Config, history, and the SQLite runtime database (`airfieldops.sqlite`) are stored in the persistent Docker volume at `/var/lib/airfieldops`.

### Reference Data Management

The project uses [OurAirports](https://ourairports.com/data/) as the primary source for global airport and runway data.

#### Refreshing Reference Data

To refresh the dataset (e.g., to get latest FAA/global updates):

1.  **Dry Run First:**
    ```bash
    ./refresh_reference_data.sh --dry-run
    ```
    This will download (if requested), parse, and validate the data without modifying your database. Review the generated report in `reports/reference_import_YYYYMMDD_HHMMSS.json`.

2.  **Execute Refresh:**
    ```bash
    ./refresh_reference_data.sh
    ```
    This script automatically:
    - Creates a backup in `backups/`.
    - Imports the data while preserving curated geometry for airports like KAVP and KAGC.
    - Runs validation checks.
    - Reports before/after counts.

#### Rollback

If an import results in bad data:

1.  Identify the latest good backup in `backups/`.
2.  Run the restore script:
    ```bash
    ./restore.sh backups/backup_YYYYMMDD_HHMMSS.tar.gz
    ```

**Warning:** Do not run `docker compose down -v` unless you intend to permanently wipe all reference data and settings.

### Public Deployment
...

When exposing AirfieldOps Core publicly, ensure the following safety measures:

1. **Read-Only Mode:** Set `PUBLIC_READONLY_MODE=true` (default) in your environment. This will block all mutating endpoints (settings, favorites, recent history) unless a valid `X-Admin-Token` is provided. In this mode, user preferences (default airport, recent search history) are stored in the user's browser `localStorage` instead of the backend database.
2. **Admin Token:** Configure a strong `ADMIN_API_TOKEN`. If this is not set while in read-only mode, all mutations will be permanently blocked for safety.
3. **Debug Endpoints:** Ensure `DEBUG_PUBLIC_ENDPOINTS=false` (default) to hide internal debugging information.
4. **User-Agent:** Set `AIRFIELDOPS_USER_AGENT` to identify your instance to AviationWeather and NWS servers.
5. **API Keys:** No API keys are currently required for AviationWeather or NWS usage.
6. **Scripts:** Do not expose backup/restore scripts through web endpoints; they should remain CLI-only for security.
7. **Auto-Refresh:** Keep `refresh_interval_seconds` at a conservative level (e.g., 300+) to avoid excessive API calls and potential rate limiting.
8. **HTTPS:** Always serve the dashboard over HTTPS when exposed to the public internet.

**Note:** This application is advisory-only. It is not for certified aviation, dispatch, or flight planning.

### Content Security Policy & Analytics

AirfieldOps Core maintains a strict Content Security Policy (CSP) to ensure security and prevent unauthorized script execution. 

1. **Analytics/Beacons:** This project does not include any analytics or tracking scripts (e.g., Google Analytics, Cloudflare Insights).
2. **CSP Violations:** If you deploy via Cloudflare and see CSP violation warnings in your browser console for `static.cloudflareinsights.com/beacon.min.js`, it is because Cloudflare is automatically injecting an analytics beacon at the edge.
3. **Disabling Analytics:** To resolve these warnings, you should **disable Web Analytics** in your Cloudflare dashboard under the "Web Analytics" or "Scrape Shield" settings for your domain. Do not weaken the app's CSP to accommodate these scripts.

## Testing
To run the test suite:
```bash
pytest
```# Dashboard
