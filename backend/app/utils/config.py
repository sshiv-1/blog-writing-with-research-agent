from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv
from langchain_google_genai import ChatGoogleGenerativeAI

# Resolve .env from project root (GenAI-AgenticAI/.env)
# Path chain: config.py -> utils/ -> app/ -> backend/ -> GenAI-AgenticAI/
_ROOT = Path(__file__).resolve().parents[3]
load_dotenv(_ROOT / ".env")

TAVILY_API_KEY: str = os.getenv("TAVILY_API_KEY", "")
# Override model via env: GEMINI_MODEL=gemini-2.0-flash
GEMINI_MODEL: str = os.getenv("GEMINI_MODEL", "gemini-3.1-flash-lite")

# Single shared LLM instance — created once at module import, reused by all nodes.
# No explicit api_key passed — LangChain automatically reads GOOGLE_API_KEY
# from the environment (set in Render dashboard).
llm = ChatGoogleGenerativeAI(
    model=GEMINI_MODEL,
    temperature=1.0,
    max_retries=2,
)

