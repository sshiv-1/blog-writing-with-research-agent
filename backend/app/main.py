from __future__ import annotations

import os

import langchain_google_genai

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .api.routes import router

app = FastAPI(
    title="Blog Writing Agent API",
    description="AI-powered technical blog generator backed by LangGraph + Gemini.",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
)

# ---------------------------------------------------------------------------
# CORS
# ---------------------------------------------------------------------------
# In development, defaults to localhost only.
# In production (Render), set the ALLOWED_ORIGINS environment variable to
# your Vercel URL, e.g.:
#   ALLOWED_ORIGINS=https://your-app.vercel.app,https://your-custom-domain.com
#
# Multiple origins are comma-separated. No trailing slashes.
# ---------------------------------------------------------------------------
_raw_origins = os.getenv(
    "ALLOWED_ORIGINS",
    "http://localhost:5173,http://127.0.0.1:5173",
)
ALLOWED_ORIGINS = [o.strip() for o in _raw_origins.split(",") if o.strip()]

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(router)


@app.get("/health", tags=["meta"])
async def health():
    """Simple liveness probe."""
    return {"status": "ok"}


# ---------------------------------------------------------------------------
# TEMPORARY — remove once auth is confirmed working on Render
# ---------------------------------------------------------------------------
@app.get("/debug-auth", tags=["meta"])
def debug_auth():
    """Exposes env var state and package versions to debug 401 auth errors."""
    key = os.environ.get("GOOGLE_API_KEY", "")
    return {
        "langchain_google_genai_version": langchain_google_genai.__version__,
        "key_exists": "GOOGLE_API_KEY" in os.environ,
        "key_length": len(key),
        "key_prefix": key[:3] if key else None,
        "has_trailing_space": key.endswith(" ") if key else False,
        "has_leading_space": key.startswith(" ") if key else False,
        "has_quotes": (key.startswith('"') or key.endswith('"')) if key else False,
    }

