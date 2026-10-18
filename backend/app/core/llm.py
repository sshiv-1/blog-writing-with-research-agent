"""
llm.py — Bring-Your-Own-Key (BYOK) multi-provider LLM factory and registry.

Slide design principles adapted from ppt-master by Hugo He (MIT).
Phase 3a: Multi-provider registry (Groq, OpenAI, Anthropic, Google, OpenRouter).
"""
from __future__ import annotations

import inspect
import os
import re
import threading
import time
from collections import deque
from pathlib import Path
from typing import Any, Optional

from dotenv import load_dotenv

from ..models.schemas import LLMSelection

# Load backend/.env with override=True so stale shell env vars don't win.
_ENV_PATH = Path(__file__).resolve().parents[2] / ".env"
load_dotenv(_ENV_PATH, override=True)

# ═══════════════════════════════════════════════════════════════════════════
# PROVIDER REGISTRY
# All supported LLM providers, model mappings, default options, and profiles.
# ALL model names in the codebase are declared exclusively in this block.
# ═══════════════════════════════════════════════════════════════════════════

PROVIDER_REGISTRY: dict[str, dict[str, Any]] = {
    "groq": {
        "name": "Groq",
        "base_url": "https://api.groq.com/openai/v1",
        "default_models": {
            "blog": "openai/gpt-oss-120b",
            "slides": "openai/gpt-oss-120b",
            "test": "openai/gpt-oss-120b",
        },
        "recommended_models": [
            "openai/gpt-oss-120b",
            "llama-3.3-70b-versatile",
        ],
        "profile": {
            "planner_input_token_cap": 4500,
            "worker_concurrency": 3,
            "max_output_tokens_blog_section": 4096,
            "max_output_tokens_slides": 4500,
        },
        "options": {
            "temperature_blog": 0.4,
            "temperature_slides": 0.2,
            "reasoning_effort": "low",
        },
    },
    "openai": {
        "name": "OpenAI",
        "base_url": "https://api.openai.com/v1",
        "default_models": {
            "blog": "gpt-6.1-sol",
            "slides": "gpt-6.1-sol",
            "test": "gpt-6.1-sol",
        },
        "recommended_models": [
            "gpt-6.1-sol",
            "gpt-6-astra",
            "gpt-6-luna",
        ],
        "profile": {
            "planner_input_token_cap": None,  # Whole article (hard ceiling: ~60k tokens)
            "worker_concurrency": 5,
            "max_output_tokens_blog_section": 4096,
            "max_output_tokens_slides": 16384,  # >= 16000 for reasoning models
        },
        "options": {
            "reasoning_effort": "low",
            "omit_temperature": True,
            "use_responses_api": True,
        },
    },
    "anthropic": {
        "name": "Anthropic",
        "base_url": "https://api.anthropic.com",
        "default_models": {
            "blog": "claude-sonnet-5-5",
            "slides": "claude-sonnet-5-5",
            "test": "claude-sonnet-5-5",
        },
        "recommended_models": [
            "claude-sonnet-5-5",
            "claude-haiku-5-5",
            "claude-opus-5-5",
        ],
        "profile": {
            "planner_input_token_cap": None,  # Whole article (hard ceiling: ~60k tokens)
            "worker_concurrency": 5,
            "max_output_tokens_blog_section": 4096,
            "max_output_tokens_slides": 16000,  # Required by Anthropic
        },
        "options": {
            "temperature_blog": 0.4,
            "temperature_slides": 0.2,
        },
    },
    "google": {
        "name": "Google",
        "base_url": None,  # Managed internally by Google SDK
        # TODO: user will paste exact model IDs
        "default_models": {
            "blog": "gemini-1.5-pro-latest",
            "slides": "gemini-1.5-pro-latest",
            "test": "gemini-1.5-pro-latest",
        },
        "recommended_models": [
            "gemini-1.5-pro-latest",
            "gemini-1.5-flash-latest",
        ],
        "profile": {
            "planner_input_token_cap": None,  # Whole article (hard ceiling: ~60k tokens)
            "worker_concurrency": 5,
            "max_output_tokens_blog_section": 4096,
            "max_output_tokens_slides": 8192,
        },
        "options": {
            "temperature_blog": 0.4,
            "temperature_slides": 0.2,
        },
    },
    "openrouter": {
        "name": "OpenRouter",
        "base_url": "https://openrouter.ai/api/v1",
        # VERIFY: IDs must match openrouter.ai/models
        "default_models": {
            "blog": "anthropic/claude-3.5-sonnet",
            "slides": "anthropic/claude-3.5-sonnet",
            "test": "anthropic/claude-3.5-sonnet",
        },
        "recommended_models": [
            "anthropic/claude-3.5-sonnet",
            "openai/gpt-4o",
            "google/gemini-pro-1.5",
            "meta-llama/llama-3.3-70b-instruct",
        ],
        "profile": {
            "planner_input_token_cap": None,  # Whole article (hard ceiling: ~60k tokens)
            "worker_concurrency": 5,
            "max_output_tokens_blog_section": 4096,
            "max_output_tokens_slides": 8192,
        },
        "options": {
            "temperature_blog": 0.4,
            "temperature_slides": 0.2,
        },
    },
}

MODEL_CHARSET_REGEX = re.compile(r"^[a-zA-Z0-9_\-\.\/:]+$")


# ═══════════════════════════════════════════════════════════════════════════
# Validation & Security Sanitization
# ═══════════════════════════════════════════════════════════════════════════

def validate_provider(provider: str) -> str:
    """Validate provider string against the fixed registry allowlist."""
    prov = (provider or "").strip().lower()
    if prov not in PROVIDER_REGISTRY:
        raise ValueError(
            f"Unsupported LLM provider '{prov}'. Supported: {', '.join(PROVIDER_REGISTRY.keys())}"
        )
    return prov


def validate_model_name(model: str) -> str:
    """Validate model name length and charset to prevent injection."""
    mod = (model or "").strip()
    if not mod or len(mod) > 128 or not MODEL_CHARSET_REGEX.match(mod):
        raise ValueError(
            "Invalid model identifier. Must be 1-128 characters containing letters, numbers, '.', '-', '_', '/', or ':'."
        )
    return mod


def scrub_secrets(text: Optional[str], keys: Optional[list[str]] = None) -> str:
    """Scrub sensitive API keys and matching patterns from any string."""
    if not text:
        return ""
    res = str(text)
    if keys:
        for k in keys:
            if k and isinstance(k, str) and len(k) >= 4:
                res = res.replace(k, "[REDACTED_API_KEY]")
    patterns = [
        r"sk-ant-[a-zA-Z0-9_\-]{10,}",
        r"sk-or-v1-[a-zA-Z0-9_\-]{10,}",
        r"sk-[a-zA-Z0-9_\-]{10,}",
        r"gsk_[a-zA-Z0-9_\-]{10,}",
        r"AIza[0-9A-Za-z\-_]{30,}",
    ]
    for pat in patterns:
        res = re.sub(pat, "[REDACTED_API_KEY]", res)
    return res


def scrub_exception_chain(exc: BaseException, keys: Optional[list[str]] = None) -> str:
    """Traverse an exception chain and return a safe, sanitized summary under 300 chars."""
    messages = []
    curr: Optional[BaseException] = exc
    visited = set()
    while curr and id(curr) not in visited:
        visited.add(id(curr))
        msg = str(curr).strip()
        if msg and msg not in messages:
            messages.append(msg)
        curr = curr.__cause__ or curr.__context__
    combined = " -> ".join(messages) if messages else "Internal error"
    scrubbed = scrub_secrets(combined, keys=keys)
    scrubbed = re.sub(r"https?://\S+", "", scrubbed).strip()
    return scrubbed[:300].strip()


# ═══════════════════════════════════════════════════════════════════════════
# IP Rate Limiting for /llm/test
# ═══════════════════════════════════════════════════════════════════════════

_IP_RATE_LIMITS: dict[str, deque[float]] = {}
_IP_LOCK = threading.Lock()


def check_ip_rate_limit(ip: str, max_reqs: int = 10, window_secs: float = 60.0) -> bool:
    """In-memory sliding window rate limiter for test probe requests per IP."""
    with _IP_LOCK:
        now = time.monotonic()
        if ip not in _IP_RATE_LIMITS:
            _IP_RATE_LIMITS[ip] = deque()
        timestamps = _IP_RATE_LIMITS[ip]
        while timestamps and timestamps[0] <= now - window_secs:
            timestamps.popleft()
        if len(timestamps) >= max_reqs:
            return False
        timestamps.append(now)
        return True


# ═══════════════════════════════════════════════════════════════════════════
# Dynamic LLM Factory
# ═══════════════════════════════════════════════════════════════════════════

def get_llm(
    role: str = "blog",
    selection: Optional[LLMSelection] = None,
    override_options: Optional[dict[str, Any]] = None,
):
    """
    Construct a chat model for the given role and selection.

    - role: "blog" | "slides" | "test"
    - selection: Optional[LLMSelection] with provider, model, api_key.
      If selection is None: falls back to the server's Groq environment keys.
      If selection has a non-Groq provider without a key: raises ValueError.
    - override_options: Optional parameter overrides for retry probes.
    """
    if role not in ("blog", "slides", "test"):
        raise ValueError(f"Invalid role '{role}'. Must be 'blog', 'slides', or 'test'.")

    # 1. Fallback mode: no selection sent, use server's Groq keys
    if selection is None:
        provider = "groq"
        provider_cfg = PROVIDER_REGISTRY["groq"]
        if role == "slides":
            api_key = os.environ.get("GROQ_PPTX_API_KEY")
            if not api_key:
                raise RuntimeError("GROQ_PPTX_API_KEY is not set. Add it to backend/.env and restart.")
            model = os.environ.get("GROQ_PPTX_MODEL", provider_cfg["default_models"]["slides"])
        else:
            api_key = os.environ.get("GROQ_BLOG_API_KEY")
            if not api_key:
                raise RuntimeError("GROQ_BLOG_API_KEY is not set. Add it to backend/.env and restart.")
            model = os.environ.get("GROQ_BLOG_MODEL", provider_cfg["default_models"]["blog"])
    else:
        # 2. BYOK mode
        provider = validate_provider(selection.provider)
        provider_cfg = PROVIDER_REGISTRY[provider]
        if selection.model:
            model = validate_model_name(selection.model)
        else:
            model = provider_cfg["default_models"][role]

        raw_key = selection.api_key.get_secret_value() if selection.api_key else None
        if not raw_key:
            raise ValueError(f"API key is required for provider '{provider}'.")
        api_key = raw_key

    profile = provider_cfg["profile"]
    options = dict(provider_cfg.get("options", {}))
    if override_options:
        options.update(override_options)

    # 3. Provider Instantiation
    if provider == "groq":
        from langchain_groq import ChatGroq

        temp = options.get(f"temperature_{role}", 0.2 if role == "slides" else 0.4)
        if options.get("omit_temperature"):
            temp = None

        kwargs: dict[str, Any] = {
            "model": model,
            "api_key": api_key,
            "max_retries": 3,
            "timeout": 90 if role == "slides" else 60,
        }
        if temp is not None:
            kwargs["temperature"] = temp

        if "gpt-oss" in model.lower() or options.get("reasoning_effort"):
            kwargs["reasoning_effort"] = options.get("reasoning_effort", "low")

        if role == "slides":
            kwargs["max_tokens"] = profile.get("max_output_tokens_slides", 4500)
        elif role == "blog":
            kwargs["max_tokens"] = profile.get("max_output_tokens_blog_section", 4096)
        elif role == "test":
            kwargs["max_tokens"] = options.get("max_tokens", 16)

        return ChatGroq(**kwargs)

    elif provider == "openai":
        from langchain_openai import ChatOpenAI

        kwargs = {
            "model": model,
            "api_key": api_key,
            "base_url": provider_cfg["base_url"],
            "max_retries": 3,
            "timeout": 90 if role == "slides" else 60,
        }
        if not options.get("omit_temperature", False):
            kwargs["temperature"] = options.get(f"temperature_{role}", 0.7)

        if "reasoning_effort" in options and options["reasoning_effort"] is not None:
            kwargs["reasoning_effort"] = options["reasoning_effort"]

        if role == "slides":
            kwargs["max_completion_tokens"] = profile.get("max_output_tokens_slides", 16384)
        elif role == "blog":
            kwargs["max_completion_tokens"] = profile.get("max_output_tokens_blog_section", 4096)
        elif role == "test":
            kwargs["max_completion_tokens"] = options.get("max_completion_tokens", 16)

        if options.get("use_responses_api"):
            try:
                sig = inspect.signature(ChatOpenAI.__init__)
                if "use_responses_api" in sig.parameters:
                    kwargs["use_responses_api"] = True
            except Exception:
                pass

        return ChatOpenAI(**kwargs)

    elif provider == "anthropic":
        from langchain_anthropic import ChatAnthropic

        temp = options.get(f"temperature_{role}", 0.2 if role == "slides" else 0.4)
        if options.get("omit_temperature"):
            temp = None

        kwargs = {
            "model": model,
            "api_key": api_key,
            "max_retries": 3,
            "timeout": 90 if role == "slides" else 60,
        }
        if temp is not None:
            kwargs["temperature"] = temp

        if role == "slides":
            kwargs["max_tokens"] = profile.get("max_output_tokens_slides", 16000)
        elif role == "blog":
            kwargs["max_tokens"] = profile.get("max_output_tokens_blog_section", 4096)
        elif role == "test":
            kwargs["max_tokens"] = options.get("max_tokens", 16)

        return ChatAnthropic(**kwargs)

    elif provider == "google":
        from langchain_google_genai import ChatGoogleGenerativeAI

        temp = options.get(f"temperature_{role}", 0.2 if role == "slides" else 0.4)
        if options.get("omit_temperature"):
            temp = None

        kwargs = {
            "model": model,
            "google_api_key": api_key,
            "max_retries": 3,
            "timeout": 90 if role == "slides" else 60,
        }
        if temp is not None:
            kwargs["temperature"] = temp

        if role == "slides":
            kwargs["max_output_tokens"] = profile.get("max_output_tokens_slides", 8192)
        elif role == "blog":
            kwargs["max_output_tokens"] = profile.get("max_output_tokens_blog_section", 4096)
        elif role == "test":
            kwargs["max_output_tokens"] = options.get("max_output_tokens", 16)

        return ChatGoogleGenerativeAI(**kwargs)

    elif provider == "openrouter":
        from langchain_openai import ChatOpenAI

        temp = options.get(f"temperature_{role}", 0.2 if role == "slides" else 0.4)
        if options.get("omit_temperature"):
            temp = None

        kwargs = {
            "model": model,
            "api_key": api_key,
            "base_url": provider_cfg["base_url"],
            "max_retries": 3,
            "timeout": 90 if role == "slides" else 60,
        }
        if temp is not None:
            kwargs["temperature"] = temp

        if role == "slides":
            kwargs["max_tokens"] = profile.get("max_output_tokens_slides", 8192)
        elif role == "blog":
            kwargs["max_tokens"] = profile.get("max_output_tokens_blog_section", 4096)
        elif role == "test":
            kwargs["max_tokens"] = options.get("max_tokens", 16)

        return ChatOpenAI(**kwargs)

    raise ValueError(f"Provider '{provider}' initialization handler not implemented.")


# Backward compatibility aliases
def blog_llm():
    """Return a ChatGroq instance configured for blog generation (legacy alias)."""
    return get_llm("blog", None)


def slides_llm():
    """Return a ChatGroq instance configured for slide deck generation (legacy alias)."""
    return get_llm("slides", None)
