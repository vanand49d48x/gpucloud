from fastapi import FastAPI
from apps.api.app import models  # Import models for Alembic
from apps.api.app import db      # Import db for Alembic
from apps.api.app.routers import auth, billing, pods, catalog

app = FastAPI(title="GPUCloud API", version="0.1.0")

@app.get("/healthz")
def health():
    return {"ok": True, "version": "0.1.0"}

app.include_router(auth.router)
app.include_router(billing.router)
app.include_router(pods.router)
app.include_router(catalog.router)
