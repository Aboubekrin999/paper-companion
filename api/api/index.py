"""
FastAPI entry point for paper-companion.

Deployed as a single Vercel Python Function. Adding endpoints means
adding routes here (or, once the surface grows, splitting into routers
included from this module).
"""

import os
from typing import Literal

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

app = FastAPI(
    title="Paper Companion API",
    description="Backend for paper-companion: PDF ingest, embeddings, RAG chat.",
    version="0.0.1",
    docs_url="/docs",
    redoc_url=None,
)

# CORS: a comma-separated allowlist via env keeps prod and local dev honest.
_allowed = os.environ.get("ALLOWED_ORIGINS", "http://localhost:3000")
allowed_origins = [o.strip() for o in _allowed.split(",") if o.strip()]

app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PATCH", "DELETE"],
    allow_headers=["*"],
)


class HealthResponse(BaseModel):
    status: Literal["ok"]
    version: str


@app.get("/health", response_model=HealthResponse, tags=["meta"])
async def health() -> HealthResponse:
    """Liveness probe. Used by uptime checks and the web app's boot ping."""
    return HealthResponse(status="ok", version=app.version)
