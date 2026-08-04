from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv
from langchain_google_genai import ChatGoogleGenerativeAI

# Resolve .env from project root (GenAI-AgenticAI/.env)
# Path chain: config.py -> utils/ -> app/ -> backend/ -> GenAI-AgenticAI/
_ROOT = Path(__file__).resolve().parents[3]
load_dotenv(_ROOT / ".env")

GEMINI_API_KEY: str = os.getenv("GEMINI_API_KEY", "")
TAVILY_API_KEY: str = os.getenv("TAVILY_API_KEY", "")
# Override via .env: GEMINI_MODEL=gemini-2.0-flash-lite
GEMINI_MODEL: str = os.getenv("GEMINI_MODEL", "gemini-3.1-flash-lite")

# Single shared LLM instance — created once at module import, reused by all nodes
llm = ChatGoogleGenerativeAI(
    model=GEMINI_MODEL,
    temperature=1.0,
    max_retries=2,
    google_api_key=GEMINI_API_KEY,
)
