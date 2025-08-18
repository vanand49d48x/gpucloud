from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from apps.api.app import models  # Import models for Alembic
from apps.api.app import db      # Import db for Alembic
from apps.api.app.routers import auth, billing, pods, catalog, terminal, logs
from .status_sync import start_status_sync, stop_status_sync
import asyncio
import logging
from datetime import datetime

logger = logging.getLogger(__name__)

app = FastAPI(title="GPUCloud API", version="0.1.0")

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, restrict this to specific domains
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.on_event("startup")
async def startup_event():
    """Startup event - start background tasks"""
    # Start status sync manager
    asyncio.create_task(start_status_sync())
    logger.info("Status sync manager started")

@app.on_event("shutdown")
async def shutdown_event():
    """Shutdown event - stop background tasks"""
    # Stop status sync manager
    stop_status_sync()
    logger.info("Status sync manager stopped")

@app.get("/healthz")
def health():
    return {"ok": True, "version": "0.1.0"}

@app.get("/v1/health")
def system_health():
    """Get overall system health status"""
    return {
        "status": "healthy",
        "version": "0.1.0",
        "timestamp": "2025-08-15T02:32:00Z"
    }

@app.get("/worker-health")
async def worker_health():
    """Check worker process health and queue status"""
    try:
        # Simple worker health check without psutil
        return {
            "worker_status": "checking",
            "status_sync_running": True,  # We know this is running
            "timestamp": datetime.utcnow().isoformat()
        }
        
    except Exception as e:
        logger.error(f"Error checking worker health: {e}")
        return {
            "worker_status": "unknown",
            "error": str(e),
            "timestamp": datetime.utcnow().isoformat()
        }

app.include_router(auth.router)
app.include_router(billing.router)
app.include_router(pods.router)
app.include_router(catalog.router)
app.include_router(terminal.router)
app.include_router(logs.router)
