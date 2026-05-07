import json
from pathlib import Path
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from fastapi.middleware.cors import CORSMiddleware
from app.api.routes import airport, weather, runways, alternates, hazards, brief, settings, reference, debug, favorites, recent_airports
from app.core.disclaimers import ADVISORY_DISCLAIMER

from contextlib import asynccontextmanager
from app.services.runtime_db import init_runtime_db_if_needed

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Initialize runtime DB on startup
    init_runtime_db_if_needed()
    yield
    # Cleanup on shutdown if needed

app = FastAPI(title="AirfieldOps Core", description=ADVISORY_DISCLAIMER, lifespan=lifespan)

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
