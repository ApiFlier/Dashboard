# Deployment Foundation

This directory contains resources for deploying the AirfieldOps Core application in a production-like environment.

## Overview
The application is designed to be run via Docker. For simple development and testing, you can use the `docker-compose.yml` in the root directory. For production, you can use the configuration provided here (`docker-compose.prod.yml`).

## Scripts
- **`setup.sh`**: Creates `.env` with production defaults, discovers a free port, builds and starts the Docker container using a named volume. It optionally cleans up source files to leave a lightweight deployment footprint.
- **`backup.sh`**: Creates a timestamped tar.gz archive of the `.env` file and the `airfieldops_state` Docker volume. (Future-proofed with placeholders for SQLite).
- **`restore.sh`**: Restores `.env` and `airfieldops_state` from a backup archive.

## Production Strategy
For a production deployment:
1. Run `./setup.sh`.
2. The setup script will pull or build the image, provision a Docker named volume (`airfieldops_state`), and start the container with a restart policy of `unless-stopped`.
3. The running app has NO bind-mount dependency on the local source folder.
4. You can safely delete the local source code (using the `DELETE SOURCE` prompt). The application will continue running and auto-restart on host reboots.

To make future updates after deleting the local files, you will need to re-clone the repository and re-run setup or deployment commands.

## Deployment Validation

To verify that your deployment is correctly decoupled from the source repository:

1. **Check the Port:** Run `./setup.sh` and confirm it prints an accessible URL (e.g., `http://localhost:8080`).
2. **Check Health:** Visit `http://localhost:8080/api/health` in your browser or via curl.
3. **Check Restart Policy:** Run `docker inspect airfieldops-app | grep RestartPolicy -A 2`. It should show `unless-stopped`.
4. **Check Mounts:** Run `docker inspect airfieldops-app | grep Mounts -A 10`. Ensure `Source` paths point to Docker volumes (`/var/lib/docker/volumes/...`) and not your local repository directory.
5. **Check Restart Resilience:** Stop the container (`docker stop airfieldops-app`) and start it again (`docker start airfieldops-app`). It should run perfectly without needing `docker-compose.yml`.
6. **Check Decoupling:** Rename the repository folder (`mv dashboard dashboard_backup`) and confirm the app is still reachable. Rename it back afterward.

**Note on Data:**
Reference airport data is shipped with the app and seeded into the SQLite runtime database (`/var/lib/airfieldops/airfieldops.sqlite`) on first run. The runtime database lives in the Docker named volume `airfieldops_state` and is never overwritten on normal restart. Live weather/hazard data is fetched fresh, and old cache is disposable. `backup.sh` backs up the Docker volume, and `restore.sh` restores it safely.