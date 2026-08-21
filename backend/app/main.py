"""
APBS Processing & Validation System — FastAPI Entry Point.
"""

from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.auth import router as auth_router
from app.api.batches import router as batches_router
from app.api.logs import router as logs_router
from app.schemas.processing import HealthCheckSchema

app = FastAPI(
    title="APBS 177-Char Processing & Validation System",
    description="Fixed-width APBS record parser with streaming I/O, "
                "duplicate detection, asynchronous queue, and human verification.",
    version="1.0.0",
)

# ── CORS ────────────────────────────────────────────────────────────
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Routers ─────────────────────────────────────────────────────────
app.include_router(auth_router)
app.include_router(batches_router)
app.include_router(logs_router)


# ── Health Check ────────────────────────────────────────────────────
@app.get("/api/health", response_model=HealthCheckSchema, tags=["system"])
async def health_check():
    """Service health check endpoint."""
    return HealthCheckSchema()
