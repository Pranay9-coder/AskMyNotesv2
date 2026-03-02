"""
FastAPI application entry point.
- CORS configuration
- Lifespan: create DB tables, ensure data directories
- Health endpoint
- Router registration
"""
from __future__ import annotations

from contextlib import asynccontextmanager
from typing import AsyncGenerator

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import settings
from app.core.logging import configure_logging, get_logger
from app.models.schema import HealthResponse
from app.routes import chat, files, study
from app.services.storage import init_db

configure_logging()
logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Application startup / shutdown."""
    settings.ensure_dirs()
    await init_db()
    logger.info("AskMyNotes backend started", extra={"version": settings.app_version})
    yield
    logger.info("AskMyNotes backend shutting down")


app = FastAPI(
    title="AskMyNotes",
    version=settings.app_version,
    description="Closed-book Q&A system grounded strictly in user-uploaded notes.",
    lifespan=lifespan,
)

# ── CORS ──────────────────────────────────────────────────────
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allowed_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Routers ───────────────────────────────────────────────────
app.include_router(files.router, prefix="/api", tags=["files"])
app.include_router(chat.router, prefix="/api", tags=["chat"])
app.include_router(study.router, prefix="/api", tags=["study"])


# ── Health ────────────────────────────────────────────────────
@app.get("/health", response_model=HealthResponse, tags=["meta"])
async def health() -> HealthResponse:
    return HealthResponse(status="ok", version=settings.app_version)
