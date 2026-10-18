"""
llm.py — Centralised LLM factory for Groq-backed blog generation.

Phase 1: blog_llm() only. PPTX model will be added in a later phase.
"""
from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

# Load backend/.env with override=True so stale shell env vars don't win.
_ENV_PATH = Path(__file__).resolve().parents[2] / ".env"
load_dotenv(_ENV_PATH, override=True)


def blog_llm():
    """Return a ChatGroq instance configured for blog generation."""
    from langchain_groq import ChatGroq

    api_key = os.environ.get("GROQ_BLOG_API_KEY")
    if not api_key:
        raise RuntimeError(
            "GROQ_BLOG_API_KEY is not set. "
            "Add it to backend/.env and restart."
        )

    model = os.environ.get("GROQ_BLOG_MODEL", "openai/gpt-oss-120b")

    return ChatGroq(
        model=model,
        temperature=0.4,
        api_key=api_key,
        max_retries=3,
        timeout=60,
    )


def slides_llm():
    """Return a ChatGroq instance configured for slide deck generation."""
    from langchain_groq import ChatGroq

    api_key = os.environ.get("GROQ_PPTX_API_KEY")
    if not api_key:
        raise RuntimeError(
            "GROQ_PPTX_API_KEY is not set. "
            "Add it to backend/.env and restart."
        )

    model = os.environ.get("GROQ_PPTX_MODEL", "openai/gpt-oss-120b")

    return ChatGroq(
        model=model,
        temperature=0.2,
        api_key=api_key,
        max_retries=3,
        timeout=90,
    )

