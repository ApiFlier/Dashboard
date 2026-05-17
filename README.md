# AirfieldOps

**AirfieldOps** is a self-hosted live aviation operations dashboard. It runs against a real airport database sourced from [OurAirports](https://ourairports.com/data/) and fetches live weather and hazard data at runtime from public aviation APIs — no API keys required.

Select any airport by ICAO code and get a consolidated view of live METARs and TAFs, runway wind analysis, nearby alternates, and regional hazard data (SIGMETs, G-AIRMETs, CWAs, PIREPs), all in one place.

> **Advisory display only.** Not for certified flight planning, dispatch, release, or operational control.

---

## Quick Start

#### 1. Install Docker
**Linux** — [Docker Engine](https://docs.docker.com/engine/install/) + Docker Compose plugin:
```bash
# Example for Ubuntu/Debian
curl -fsSL https://get.docker.com | sudo sh
```

### 2. Verify Docker

```bash
docker --version
docker compose version
```

Both commands must succeed before proceeding.

### 3. Clone, configure, and run

```bash
git clone https://github.com/ApiFlier/airfieldops-dashboard.git airfieldops
cd airfieldops
chmod +x setup.sh
./setup.sh
```

`setup.sh` handles everything automatically:

- Creates `.env` with production-ready defaults (no editing required)
- Builds the Docker image
- Creates or reuses a Docker-managed persistent volume (`airfieldops_state`)
- Scans for an available host port starting at 8080 — **no manual port editing needed**
- Starts the container with `restart: unless-stopped`
- Prints the local URL when the app is healthy

---

## What AirfieldOps Does

Select any airport by ICAO code and get a consolidated operational view:

- **Live weather** — current METAR and TAF
- **Runway wind analysis** — headwind and crosswind components per runway, from live wind data
- **Alternate ranking** — nearby airports scored by weather, distance, and runway length
- **Hazard feed** — SIGMETs, G-AIRMETs, CWAs, and PIREPs for the region
- **Operational brief** — single-page pre-flight or ops overview

Designed for small airports, FBOs, flight schools, and charter operators who need quick operational awareness without switching between multiple browser tabs.

---

## Key Features

- Unified dashboard — weather, runways, alternates, and hazards in one place
- Fetches fresh data on demand from free public APIs; no API keys required
- Runway heading math with headwind/crosswind per runway from live METAR wind
- Alternate ranker with configurable scoring
- Public read-only mode — all mutations blocked without `X-Admin-Token`
- User preferences (default airport, favorites, recents) stored in browser `localStorage` in public mode
- No analytics, no tracking, no third-party beacons
- Strict Content Security Policy enforced server-side

---

## Architecture

```
Browser (Vanilla JS SPA)
    │
    └── FastAPI (Python 3.12, Uvicorn)
            │
            ├── AviationWeather.gov  (METAR, TAF, SIGMET, G-AIRMET, PIREP, CWA)
            ├── NWS api.weather.gov  (Alerts, Point Forecasts)
            └── SQLite               (real airport/runway/frequency database + settings)
                    Stored in Docker named volume: airfieldops_state
```

No build step or Node runtime is required. The frontend is vanilla JavaScript served as static files by the backend.

---

## Tech Stack

| Layer | Technology |
|-------|-----------|
| Backend | Python 3.12, FastAPI, Uvicorn |
| Frontend | Vanilla JavaScript, HTML/CSS (no framework, no build step) |
| Database | SQLite via Python stdlib `sqlite3` |
| Containerization | Docker, Docker Compose |
| Testing | pytest |

---

## Data Sources

| Source | Data Provided |
|--------|--------------|
| [AviationWeather.gov](https://aviationweather.gov) | METAR, TAF, PIREP, SIGMET, G-AIRMET, CWA, airport/station info |
| [NWS api.weather.gov](https://api.weather.gov) | Weather alerts, point forecasts |
| [OurAirports](https://ourairports.com/data/) | Real-world airport and runway database, frequencies (public domain, global coverage) |

No API keys are required for any data source.

**Intentional non-goals:**
- No OpenSky or flight tracking
- No NOTAMs (out of scope for current version)
- No SWIM integration
- Not a certified flight planning or dispatch tool

---

## Public Read-Only Mode / Security Model

`PUBLIC_READONLY_MODE=true` is the default. In this mode:

- All `GET` (read) endpoints are publicly accessible
- All mutating endpoints (settings, favorites, recent history) require an `X-Admin-Token` header matching `ADMIN_API_TOKEN`
- If `ADMIN_API_TOKEN` is not set, all mutations are **permanently blocked**
- User preferences fall back to browser `localStorage` automatically

Recommended settings for public deployments:

| Variable | Value | Purpose |
|----------|-------|---------|
| `PUBLIC_READONLY_MODE` | `true` | Block mutations without admin token |
| `ADMIN_API_TOKEN` | Strong random string | Required to allow any backend mutations |
| `DEBUG_PUBLIC_ENDPOINTS` | `false` | Hide internal debug endpoints |
| `AIRFIELDOPS_USER_AGENT` | Your contact info | Identifies your instance to upstream APIs |

Always serve over HTTPS when publicly exposed. Backup and restore scripts are CLI-only and are not exposed as web endpoints.

> **Ops Mode and public deployments:** If you expose this instance publicly, ensure you have changed the default Ops Mode credentials (`meeks / meeks`) before doing so. Ops Mode endpoints are protected by their own login, but the default credentials are well-known. See the [Ops Mode](#ops-mode) section below.

**Content Security Policy:** The app enforces a strict CSP. If you deploy behind Cloudflare and see CSP violation warnings for `static.cloudflareinsights.com`, disable Web Analytics in your Cloudflare dashboard rather than weakening the CSP.

---

## Ops Mode

Ops Mode is a private administrative area for operational records. It is separate from the public read-only dashboard and requires its own login.

Public AirfieldOps pages (weather, runways, hazards, alternates) remain read-only and accessible without Ops login. Ops Mode — including the overview dashboard and all operational records — requires admin authentication.

Navigate to `#/ops` to access Ops Mode.

| Feature | Status |
|---------|--------|
| **Overview Dashboard** | Available — private snapshot of today's activity, needs-attention items, and recent records across all Ops workflows |
| **Daily Ops Log** | Available — record operational events, weather observations, runway status, and shift entries per airport |
| **Shift Handoff** | Available — structured shift-change notes with weather summary, operations summary, and open items |
| **Inspection Checklist** | Available — internal field/facility review notes and operational awareness; not a certified inspection compliance system |
| **Maintenance Reminders** | Available — internal follow-up tracking and awareness; not a certified maintenance management or compliance system |

### Default Admin Login

When the container first starts, a default admin account is created automatically:

```
Username: meeks
Password: meeks
```

> **Change these immediately after first login.**
> Do not expose Ops Mode publicly without changing the default credentials.

Go to `#/ops` → **Change Credentials** to update username and password. Credentials are stored hashed (bcrypt) in the runtime SQLite database inside the Docker named volume and persist across container rebuilds.

### Ops Mode Security Model

| Aspect | Behavior |
|--------|----------|
| Access control | Username/password login; session token (24 h TTL) |
| Credential storage | bcrypt hash in `admin_users` SQLite table, inside the Docker volume |
| Backend protection | All `/api/ops/*` endpoints (including the overview dashboard) require a valid session Bearer token or `X-Admin-Token` |
| Session storage | Token kept in browser `localStorage` for persistence across tabs and restarts — acceptable for a self-hosted operator machine; do not share the browser profile |
| Public dashboard | Completely unaffected — read-only behavior is unchanged |
| Default credentials | `meeks / meeks` on first run only; change immediately |

### Ops Log Categories

`General` · `Weather` · `Runway` · `Hazard` · `Maintenance` · `Security` · `Other`

### Ops Log Severities

`Info` · `Advisory` · `Warning` · `Critical`

---

## Runtime State and Persistence

All persistent state lives in Docker named volume `airfieldops_state`, mounted at `/var/lib/airfieldops` inside the container:

| File | Purpose |
|------|---------|
| `airfieldops.sqlite` | Real airport/runway/frequency database, settings, favorites |

The airport database (sourced from OurAirports plus hand-curated geometry for airports like KAVP and KAGC) is seeded on first run. Weather cache is in-memory and disposable — a restart loses no airport data.

**Backup and restore:**
```bash
./backup.sh                                          # Timestamped archive in backups/
./restore.sh backups/backup_YYYYMMDD_HHMMSS.tar.gz  # Restore from archive
```

`restore.sh` creates a pre-restore backup and requires typed confirmation before overwriting state.

> **Warning:** `docker compose down -v` permanently wipes the named volume. Use `docker compose down` (without `-v`) for a normal stop.

**Refreshing the airport database** from OurAirports inside a running container:
```bash
./refresh_reference_data.sh --dry-run   # Preview import changes
./refresh_reference_data.sh             # Apply (auto-creates backup first)
```

---

## Testing

```bash
pytest
```

The test suite covers:

- API route response shapes
- Public read-only safety (mutations blocked without valid token)
- Runway math (headwind/crosswind calculations)
- Alternate ranking logic
- Weather normalization
- Airport database seeding and OurAirports import
- Database initialization and schema

---

## Deployment Notes

### Standard deployment

```bash
./setup.sh
```

Handles `.env` creation, port discovery, volume provisioning, image build, and health check in one step.

### Updating a running deployment

```bash
./update.sh
```

Creates a pre-update backup, rebuilds the image, and restarts the container.

### Production decoupling

Once the container is running, it has no dependency on the local source directory. You can delete the source files if desired — the app continues running and restarts on host reboot. To update after deleting source files, re-clone and run `./setup.sh`.

### Development mode

For local development with live-reload:
```bash
docker compose up --build
```

This uses a local bind mount so source changes are reflected immediately. For development only — do not use in production.

---

## Known Limitations

- **Single-airport view** — no side-by-side multi-airport comparison
- **No NOTAMs** — NOTAM parsing and display are out of scope for the current version
- **No offline mode** — weather data is fetched live on every request
- **Upstream API availability** — if AviationWeather.gov or NWS is unavailable, the dashboard degrades gracefully with warnings
- **Advisory only** — not for certified flight planning, dispatch, or operational control

---

## Roadmap / Future Work

- NOTAM display (pending a suitable free or low-cost API)
- Multi-airport comparison board
- SWIM integration for live traffic data
- User-configurable alert thresholds
- Improved mobile layout
