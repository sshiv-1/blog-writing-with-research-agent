from __future__ import annotations

import os
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from .api.routes import router
from .core.db import cleanup_stale_jobs_on_startup
from .core.llm import scrub_exception_chain


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan: clean up stale jobs on startup."""
    cleanup_stale_jobs_on_startup()
    yield


app = FastAPI(
    title="SAGE API",
    description="AI-powered research and writing studio backed by LangGraph + Groq with BYOK and Supabase persistence.",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan,
)

# ---------------------------------------------------------------------------
# CORS
# ---------------------------------------------------------------------------
_DEFAULT_ORIGINS = ["http://localhost:5173", "http://127.0.0.1:5173"]
_env_origins = [
    o.strip()
    for o in (os.getenv("CORS_ORIGINS") or os.getenv("ALLOWED_ORIGINS") or "").split(",")
    if o.strip() and o.strip() != "*"
]
ALLOWED_ORIGINS = list(dict.fromkeys(_DEFAULT_ORIGINS + _env_origins))

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=[
        "Authorization",
        "Content-Type",
        "Accept",
        "Origin",
        "User-Agent",
        "X-LLM-Provider",
        "X-LLM-Model",
        "X-LLM-Key",
        "X-LLM-Slides-Provider",
        "X-LLM-Slides-Model",
    ],
    expose_headers=["Content-Disposition"],
)


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    """Global exception handler ensuring unhandled exceptions never expose secrets or headers."""
    scrubbed = scrub_exception_chain(exc)
    return JSONResponse(
        status_code=500,
        content={"detail": scrubbed or "Internal server error"},
    )


app.include_router(router)


@app.get("/health", tags=["meta"])
async def health():
    """Simple liveness probe."""
    return {"status": "ok"}
