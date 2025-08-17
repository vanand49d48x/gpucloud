from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from apps.api.app import models  # Import models for Alembic
from apps.api.app import db      # Import db for Alembic
from apps.api.app.routers import auth, billing, pods, catalog, terminal, logs

app = FastAPI(title="GPUCloud API", version="0.1.0")

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, restrict this to specific domains
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

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

app.include_router(auth.router)
app.include_router(billing.router)
app.include_router(pods.router)
app.include_router(catalog.router)
app.include_router(terminal.router)
app.include_router(logs.router)
