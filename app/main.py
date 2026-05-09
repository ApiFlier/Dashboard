import json
from pathlib import Path
from fastapi import FastAPI, Request
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from fastapi.middleware.cors import CORSMiddleware
from app.api.routes import airport, weather, runways, alternates, hazards, brief, settings, reference, debug, favorites, recent_airports
from app.api.routes import ops as ops_routes
from app.core.disclaimers import ADVISORY_DISCLAIMER

from contextlib import asynccontextmanager
from app.services.runtime_db import init_runtime_db_if_needed
from app.services.ops_auth import bootstrap_default_admin

@asynccontextmanager
async def lifespan(app: FastAPI):
    init_runtime_db_if_needed()
    bootstrap_default_admin()
    yield

app = FastAPI(title="AirfieldOps Core", description=ADVISORY_DISCLAIMER, lifespan=lifespan)

@app.middleware("http")
async def add_security_headers(request: Request, call_next):
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    response.headers["X-Frame-Options"] = "SAMEORIGIN"
    # Basic CSP: allow self, and common aviation data sources
    response.headers["Content-Security-Policy"] = (
        "default-src 'self'; "
        "script-src 'self' 'unsafe-inline'; "
        "style-src 'self' 'unsafe-inline'; "
        "img-src 'self' data: https://*.faa.gov https://*.weather.gov; "
        "connect-src 'self' https://aviationweather.gov https://api.weather.gov;"
    )
    return response

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# API Routes
app.include_router(airport.router, prefix="/api")
app.include_router(weather.router, prefix="/api")
app.include_router(runways.router, prefix="/api")
app.include_router(alternates.router, prefix="/api")
app.include_router(hazards.router, prefix="/api")
app.include_router(brief.router, prefix="/api")
app.include_router(settings.router, prefix="/api")
app.include_router(favorites.router, prefix="/api", tags=["favorites"])
app.include_router(recent_airports.router, prefix="/api", tags=["recent"])
app.include_router(reference.router, prefix="/api/reference", tags=["reference"])
app.include_router(debug.router, prefix="/api/debug", tags=["debug"])
app.include_router(ops_routes.router, prefix="/api", tags=["ops"])

@app.get("/api/health")
async def health_check():
    return {"status": "ok", "disclaimer": ADVISORY_DISCLAIMER}

# Mount static files
app.mount("/static", StaticFiles(directory="app/static"), name="static")

@app.get("/{full_path:path}")
async def serve_spa(full_path: str):
    if full_path.startswith("api/"):
        return {"error": "API route not found"}
    return FileResponse("app/static/index.html")
