from __future__ import annotations

import logging
import os
import re
import threading
import time
from collections import defaultdict
from typing import Literal, Optional

from fastapi import APIRouter, BackgroundTasks, Depends, Header, HTTPException, Query, Request
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import Response

from ..core import db
from ..core.agent import generate_blog
from ..core.auth import AuthUser, get_current_user, get_optional_user
from ..core.crypto import decrypt_key, encrypt_key
from ..core.jobs import (
    create_job,
    create_slide_job,
    delete_job_record,
    get_job,
    get_slide_job,
    get_user_memory_quota_counts,
    register_user_task_start,
    safe_ascii_title,
)
from ..core.llm import (
    PROVIDER_REGISTRY,
    check_ip_rate_limit,
    get_llm,
    scrub_exception_chain,
    validate_model_name,
    validate_provider,
)
from ..core.slides import generate_slides_for_blog
from ..models.schemas import (
    BlogResult,
    GenerateRequest,
    GenerateSlidesRequest,
    JobStatusResponse,
    LLMSelection,
    LLMTestResponse,
    PaginatedUserJobs,
    SaveKeyRequest,
    SlideJobStatusResponse,
    UserJobSummary,
    UserKeyItem,
)

logger = logging.getLogger("app.api.routes")
router = APIRouter()

# ---------------------------------------------------------------------------
# Abuse & Rate Limiting Configurations
# Note: Guest rate limiting is a soft in-memory abuse control to protect server resources.
# ---------------------------------------------------------------------------
GUEST_JOBS_PER_HOUR = int(os.getenv("GUEST_JOBS_PER_HOUR", "20"))
GUEST_BYOK_JOBS_PER_HOUR = int(os.getenv("GUEST_BYOK_JOBS_PER_HOUR", "30"))
DAILY_USER_JOB_CAP = int(os.getenv("DAILY_USER_JOB_CAP", "50"))
MAX_CONCURRENT_USER_JOBS = int(os.getenv("MAX_CONCURRENT_USER_JOBS", "3"))
TRUST_PROXY = os.getenv("TRUST_PROXY", "").strip().lower() in ("true", "1")
_MAX_RATE_LIMIT_KEYS = 10000

_rate_limit_lock = threading.Lock()
_user_quota_lock = threading.Lock()
_guest_job_timestamps: dict[str, list[float]] = defaultdict(list)
_guest_byok_job_timestamps: dict[str, list[float]] = defaultdict(list)
_user_key_save_timestamps: dict[str, list[float]] = defaultdict(list)


def _get_client_ip(request: Request) -> str:
    """
    Extract client IP for rate limiting.
    When TRUST_PROXY is enabled (e.g. behind Render or a reverse proxy),
    uses the LAST entry across all X-Forwarded-For headers (the IP appended
    by the trusted proxy), falling back to request.client.host.
    """
    if TRUST_PROXY:
        xff_headers = request.headers.getlist("X-Forwarded-For")
        if xff_headers:
            parts: list[str] = []
            for hdr in xff_headers:
                parts.extend(p.strip() for p in hdr.split(",") if p.strip())
            if parts:
                return parts[-1]
    return request.client.host if request.client else "unknown"


def _consume_sliding_window(
    buckets: dict[str, list[float]],
    key: str,
    window_secs: float,
    limit: int,
) -> bool:
    """Thread-safe bounded sliding window counter."""
    now = time.time()
    cutoff = now - window_secs
    with _rate_limit_lock:
        if len(buckets) >= _MAX_RATE_LIMIT_KEYS:
            stale_keys = [
                k for k, ts_list in buckets.items()
                if not ts_list or ts_list[-1] <= cutoff
            ]
            for k in stale_keys:
                del buckets[k]
            while len(buckets) >= _MAX_RATE_LIMIT_KEYS:
                buckets.pop(next(iter(buckets)))
        timestamps = [t for t in buckets.get(key, ()) if t > cutoff]
        if len(timestamps) >= limit:
            if timestamps:
                buckets[key] = timestamps
            else:
                buckets.pop(key, None)
            return False
        timestamps.append(now)
        buckets[key] = timestamps
        return True


def _check_guest_rate_limit(client_ip: str) -> bool:
    """Sliding window check for guest requests using server Groq keys (default 20/hr)."""
    return _consume_sliding_window(_guest_job_timestamps, client_ip, 3600.0, GUEST_JOBS_PER_HOUR)


def _check_guest_byok_rate_limit(client_ip: str) -> bool:
    """Sliding window check for guest BYOK requests that still touch server Tavily/TeX resources."""
    return _consume_sliding_window(_guest_byok_job_timestamps, client_ip, 3600.0, GUEST_BYOK_JOBS_PER_HOUR)


def _check_user_key_save_rate_limit(user_id: str) -> bool:
    """Allow up to 10 key save operations per minute per user."""
    return _consume_sliding_window(_user_key_save_timestamps, user_id, 60.0, 10)


def _check_user_job_limits(user_id: str) -> None:
    """Enforce daily job limit and max concurrent jobs for signed-in users (fail closed on DB errors)."""
    try:
        db_active = db.count_user_active_jobs_db(user_id)
        db_daily = db.count_user_daily_jobs_db(user_id)
    except Exception:
        raise HTTPException(
            status_code=503,
            detail="Job quota verification service is temporarily unavailable. Please retry shortly.",
        )

    mem_active, mem_daily = get_user_memory_quota_counts(user_id)
    active_count = max(db_active, mem_active)
    daily_count = max(db_daily, mem_daily)

    if active_count >= MAX_CONCURRENT_USER_JOBS:
        raise HTTPException(
            status_code=429,
            detail=f"Too many concurrent jobs in progress (max {MAX_CONCURRENT_USER_JOBS}). Please wait for current jobs to complete.",
        )

    if daily_count >= DAILY_USER_JOB_CAP:
        raise HTTPException(
            status_code=429,
            detail=f"Daily job creation limit reached ({DAILY_USER_JOB_CAP} jobs/day).",
        )


# ---------------------------------------------------------------------------
# LLM Selection Resolution
# ---------------------------------------------------------------------------

def _resolve_selection(
    role: str,
    provider_hdr: Optional[str],
    model_hdr: Optional[str],
    key_hdr: Optional[str],
    user: Optional[AuthUser] = None,
) -> Optional[LLMSelection]:
    """
    Resolve and validate LLM selection from request headers or saved user keys.
    - If neither provider nor key is provided: returns None (server Groq fallback).
    - If provider is provided:
        1. Checks key_hdr.
        2. If key_hdr is missing and user is signed in: checks saved key in user_api_keys.
        3. If no key available: raises HTTP 400.
    """
    if not provider_hdr and not key_hdr:
        return None

    if not provider_hdr:
        raise HTTPException(
            status_code=400,
            detail="X-LLM-Provider header is required when providing an API key.",
        )

    try:
        prov = validate_provider(provider_hdr)
    except ValueError as ve:
        raise HTTPException(status_code=400, detail=str(ve))

    resolved_key = key_hdr

    # Try resolving from saved keys for signed-in user if header omitted
    if not resolved_key and user:
        saved = db.get_user_key_db(user.id, prov)
        if saved:
            encrypted_key, _ = saved
            try:
                resolved_key = decrypt_key(encrypted_key)
            except Exception as dec_err:
                logger.warning("Failed to decrypt saved key for provider %s: %s", prov, scrub_exception_chain(dec_err))
                raise HTTPException(
                    status_code=500,
                    detail=f"Failed to decrypt saved API key for provider '{prov}'. Please re-enter your key.",
                )

    if not resolved_key:
        raise HTTPException(
            status_code=400,
            detail=f"API key is required for provider '{prov}'.",
        )

    if model_hdr:
        try:
            mod = validate_model_name(model_hdr)
        except ValueError as ve:
            raise HTTPException(status_code=400, detail=str(ve))
    else:
        mod = PROVIDER_REGISTRY[prov]["default_models"][role]

    selection = LLMSelection(provider=prov, model=mod, api_key=resolved_key)
    # Clear plaintext string reference
    resolved_key = None
    return selection


# ---------------------------------------------------------------------------
# Blog Generation Endpoints
# ---------------------------------------------------------------------------

@router.post("/generate", response_model=JobStatusResponse, status_code=202)
async def start_generation(
    req: GenerateRequest,
    request: Request,
    background_tasks: BackgroundTasks,
    user: Optional[AuthUser] = Depends(get_optional_user),
    x_llm_provider: Optional[str] = Header(None, alias="X-LLM-Provider"),
    x_llm_model: Optional[str] = Header(None, alias="X-LLM-Model"),
    x_llm_key: Optional[str] = Header(None, alias="X-LLM-Key"),
):
    """
    Start a blog generation job.
    Accepts optional Bearer auth token.
    Enforces guest rate limiting or signed-in user job caps.
    """
    selection = _resolve_selection("blog", x_llm_provider, x_llm_model, x_llm_key, user=user)

    non_secret_params = {
        "tone": req.tone,
        "length": req.length,
        "style": req.style,
        "audience": req.audience,
        "use_web": req.use_web,
    }

    # Abuse controls & atomic quota reservation
    if user is None:
        client_ip = _get_client_ip(request)
        if selection is None:  # Using server Groq key
            if not _check_guest_rate_limit(client_ip):
                raise HTTPException(
                    status_code=429,
                    detail=f"Guest hourly limit of {GUEST_JOBS_PER_HOUR} jobs reached. Please provide your own API key or sign in.",
                )
        elif not _check_guest_byok_rate_limit(client_ip):
            raise HTTPException(
                status_code=429,
                detail=f"Guest BYOK hourly limit of {GUEST_BYOK_JOBS_PER_HOUR} jobs reached. Please sign in to continue.",
            )
        record = create_job(
            user_id=None,
            topic=req.topic,
            params=non_secret_params,
        )
    else:
        with _user_quota_lock:
            _check_user_job_limits(user.id)
            record = create_job(
                user_id=user.id,
                topic=req.topic,
                params=non_secret_params,
            )
            register_user_task_start(user.id)

    background_tasks.add_task(
        generate_blog,
        job_id=record.job_id,
        topic=req.topic,
        tone=req.tone,
        length=req.length,
        style=req.style,
        audience=req.audience,
        use_web=req.use_web,
        llm_selection=selection,
        tracked_user_id=user.id if user else None,
    )
    return JobStatusResponse(
        job_id=record.job_id,
        status="queued",
        stage="queued",
        progress=0,
    )


@router.get("/jobs/{job_id}", response_model=JobStatusResponse)
async def get_job_status(
    job_id: str,
    user: Optional[AuthUser] = Depends(get_optional_user),
):
    """Poll the progress of a generation job. Enforces owner isolation."""
    record = get_job(job_id)
    if record is None:
        raise HTTPException(status_code=404, detail="Job not found")

    # Isolation check: if user_id is set, caller must match; otherwise 404
    if record.user_id is not None:
        if user is None or user.id != record.user_id:
            raise HTTPException(status_code=404, detail="Job not found")

    return JobStatusResponse(
        job_id=record.job_id,
        status=record.status,
        stage=record.stage,
        progress=record.progress,
        error=record.error,
    )


@router.get("/jobs/{job_id}/result", response_model=BlogResult)
async def get_job_result(
    job_id: str,
    user: Optional[AuthUser] = Depends(get_optional_user),
):
    """Fetch the final blog output. Enforces owner isolation."""
    record = get_job(job_id)
    if record is None:
        raise HTTPException(status_code=404, detail="Job not found")

    if record.user_id is not None:
        if user is None or user.id != record.user_id:
            raise HTTPException(status_code=404, detail="Job not found")

    if record.status == "error":
        raise HTTPException(status_code=500, detail=record.error or "Generation failed")
    if record.status != "done":
        raise HTTPException(
            status_code=409,
            detail=f"Job not done yet (status: {record.status}, stage: {record.stage})",
        )
    if record.result is None:
        raise HTTPException(status_code=500, detail="Job marked done but result is missing")
    return BlogResult(**record.result)


# ---------------------------------------------------------------------------
# Slide Endpoints
# ---------------------------------------------------------------------------

@router.post("/jobs/{job_id}/slides", response_model=SlideJobStatusResponse, status_code=202)
async def start_slides_generation(
    job_id: str,
    req: GenerateSlidesRequest,
    request: Request,
    background_tasks: BackgroundTasks,
    user: Optional[AuthUser] = Depends(get_optional_user),
    x_llm_slides_provider: Optional[str] = Header(None, alias="X-LLM-Slides-Provider"),
    x_llm_provider: Optional[str] = Header(None, alias="X-LLM-Provider"),
    x_llm_slides_model: Optional[str] = Header(None, alias="X-LLM-Slides-Model"),
    x_llm_model: Optional[str] = Header(None, alias="X-LLM-Model"),
    x_llm_key: Optional[str] = Header(None, alias="X-LLM-Key"),
):
    """Trigger slide generation from a completed blog job. Enforces owner isolation."""
    prov_hdr = x_llm_slides_provider or x_llm_provider
    model_hdr = x_llm_slides_model or x_llm_model
    selection = _resolve_selection("slides", prov_hdr, model_hdr, x_llm_key, user=user)

    blog_record = get_job(job_id)
    if blog_record is None:
        raise HTTPException(status_code=404, detail="Blog job not found")

    if blog_record.user_id is not None:
        if user is None or user.id != blog_record.user_id:
            raise HTTPException(status_code=404, detail="Blog job not found")

    if blog_record.status != "done":
        raise HTTPException(
            status_code=409,
            detail=f"Blog job is not completed yet (status: {blog_record.status}, stage: {blog_record.stage})",
        )

    existing_slide = get_slide_job(job_id)
    if existing_slide is not None:
        if existing_slide.user_id is not None and (user is None or user.id != existing_slide.user_id):
            raise HTTPException(status_code=404, detail="Blog job not found")
        if existing_slide.status in ("queued", "running"):
            raise HTTPException(
                status_code=409,
                detail="Slide generation is already in progress for this job.",
            )

    # Keep slide ownership consistent with parent blog job to avoid split-brain & FK orphans
    effective_slide_owner = blog_record.user_id

    # Abuse controls & atomic quota reservation
    if user is None:
        client_ip = _get_client_ip(request)
        if selection is None:
            if not _check_guest_rate_limit(client_ip):
                raise HTTPException(
                    status_code=429,
                    detail=f"Guest hourly limit of {GUEST_JOBS_PER_HOUR} jobs reached. Please provide your own API key or sign in.",
                )
        elif not _check_guest_byok_rate_limit(client_ip):
            raise HTTPException(
                status_code=429,
                detail=f"Guest BYOK hourly limit of {GUEST_BYOK_JOBS_PER_HOUR} jobs reached. Please sign in to continue.",
            )
        create_slide_job(job_id, user_id=effective_slide_owner)
    else:
        with _user_quota_lock:
            _check_user_job_limits(user.id)
            create_slide_job(job_id, user_id=effective_slide_owner)
            register_user_task_start(user.id)

    background_tasks.add_task(
        generate_slides_for_blog,
        job_id=job_id,
        slide_count=req.slide_count,
        audience=req.audience,
        llm_selection=selection,
        tracked_user_id=user.id if user else None,
    )
    return SlideJobStatusResponse(
        job_id=job_id,
        status="queued",
        stage="queued",
        progress=0,
        slide_count=req.slide_count,
        warnings=[],
        error=None,
    )


@router.get("/jobs/{job_id}/slides", response_model=SlideJobStatusResponse)
async def get_slide_job_status(
    job_id: str,
    user: Optional[AuthUser] = Depends(get_optional_user),
):
    """Poll progress of a slide generation job. Enforces owner isolation."""
    slide_job = get_slide_job(job_id)
    if slide_job is None:
        blog_record = get_job(job_id)
        if blog_record is None:
            raise HTTPException(status_code=404, detail="Job not found")
        if blog_record.user_id is not None:
            if user is None or user.id != blog_record.user_id:
                raise HTTPException(status_code=404, detail="Job not found")
        raise HTTPException(status_code=404, detail="Slide generation not started for this job")

    if slide_job.user_id is not None:
        if user is None or user.id != slide_job.user_id:
            raise HTTPException(status_code=404, detail="Job not found")

    return SlideJobStatusResponse(
        job_id=slide_job.job_id,
        status=slide_job.status,
        stage=slide_job.stage,
        progress=slide_job.progress,
        slide_count=slide_job.slide_count,
        warnings=slide_job.warnings,
        error=slide_job.error,
    )


@router.get("/jobs/{job_id}/slides/download")
async def download_slides_artifact(
    job_id: str,
    format: Literal["pdf", "pptx", "tex"] = Query("pdf"),
    user: Optional[AuthUser] = Depends(get_optional_user),
):
    """Download generated slides artifact (pdf, pptx, or tex). Streams from memory or Supabase storage."""
    slide_job = get_slide_job(job_id)
    if slide_job is None:
        raise HTTPException(status_code=404, detail="Slide job not found")

    if slide_job.user_id is not None:
        if user is None or user.id != slide_job.user_id:
            raise HTTPException(status_code=404, detail="Slide job not found")

    if slide_job.status == "error":
        raise HTTPException(status_code=500, detail=slide_job.error or "Slide generation failed")
    if slide_job.status != "done":
        raise HTTPException(
            status_code=409,
            detail=f"Slide job not completed yet (status: {slide_job.status}, stage: {slide_job.stage})",
        )

    safe_title = safe_ascii_title(slide_job.title)

    if format == "pdf":
        pdf_bytes = slide_job.pdf_bytes
        if not pdf_bytes and slide_job.user_id:
            pdf_bytes = db.get_artifact_storage(slide_job.user_id, job_id, f"{safe_title}.pdf")
        if not pdf_bytes:
            raise HTTPException(
                status_code=404,
                detail="PDF artifact not available. A LaTeX engine may not be installed on the server.",
            )
        return Response(
            content=pdf_bytes,
            media_type="application/pdf",
            headers={"Content-Disposition": f'attachment; filename="{safe_title}.pdf"'},
        )
    elif format == "pptx":
        pptx_bytes = slide_job.pptx_bytes
        if not pptx_bytes and slide_job.user_id:
            pptx_bytes = db.get_artifact_storage(slide_job.user_id, job_id, f"{safe_title}.pptx")
        if not pptx_bytes:
            raise HTTPException(status_code=404, detail="PPTX artifact not available.")
        return Response(
            content=pptx_bytes,
            media_type="application/vnd.openxmlformats-officedocument.presentationml.presentation",
            headers={"Content-Disposition": f'attachment; filename="{safe_title}.pptx"'},
        )
    elif format == "tex":
        tex_bytes = slide_job.tex_content.encode("utf-8") if slide_job.tex_content else None
        if not tex_bytes and slide_job.user_id:
            tex_bytes = db.get_artifact_storage(slide_job.user_id, job_id, f"{safe_title}.tex")
        if not tex_bytes:
            raise HTTPException(status_code=404, detail="TeX source artifact not available.")
        return Response(
            content=tex_bytes,
            media_type="text/x-tex; charset=utf-8",
            headers={"Content-Disposition": f'attachment; filename="{safe_title}.tex"'},
        )


# ---------------------------------------------------------------------------
# Authenticated User Job History & Deletion
# ---------------------------------------------------------------------------

@router.get("/me/jobs", response_model=PaginatedUserJobs)
async def get_user_jobs(
    user: AuthUser = Depends(get_current_user),
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
):
    """Return paginated list of user's jobs sorted newest first."""
    rows, total = db.list_user_jobs_db(user.id, limit=limit, offset=offset)
    items = []
    for r in rows:
        created_dt = db._parse_iso_datetime(r.get("created_at"))
        items.append(
            UserJobSummary(
                job_id=r["id"],
                topic=r.get("topic") or "",
                status=r.get("status", "queued"),
                stage=r.get("stage", "queued"),
                progress=r.get("progress", 0),
                created_at=created_dt or r.get("created_at"),
                has_slides=bool(r.get("has_slides", False)),
            )
        )
    return PaginatedUserJobs(items=items, total=total, limit=limit, offset=offset)


@router.delete("/jobs/{job_id}")
async def delete_job(
    job_id: str,
    user: Optional[AuthUser] = Depends(get_optional_user),
):
    """Delete a job and its associated slides/artifacts. Owner or guest holder only."""
    rec = get_job(job_id)
    if rec is None:
        raise HTTPException(status_code=404, detail="Job not found")

    if rec.user_id is not None:
        if user is None or user.id != rec.user_id:
            raise HTTPException(status_code=404, detail="Job not found")

    slide_rec = get_slide_job(job_id)
    if slide_rec is not None and slide_rec.user_id is not None:
        if user is None or user.id != slide_rec.user_id:
            raise HTTPException(status_code=404, detail="Job not found")

    owner_id = rec.user_id or (slide_rec.user_id if slide_rec else None)
    delete_job_record(job_id, user_id=owner_id)
    return {"ok": True, "job_id": job_id}


# ---------------------------------------------------------------------------
# Authenticated User Saved Keys (BYOK)
# ---------------------------------------------------------------------------

@router.get("/me/keys", response_model=list[UserKeyItem])
async def list_user_saved_keys(user: AuthUser = Depends(get_current_user)):
    """Return list of saved API keys for current user: [{provider, last4, created_at}]. Never returns key bytes."""
    keys = db.list_user_keys_db(user.id)
    items = []
    for k in keys:
        created_dt = db._parse_iso_datetime(k.get("created_at")) if isinstance(k.get("created_at"), str) else k.get("created_at")
        items.append(
            UserKeyItem(
                provider=k["provider"],
                last4=k["last4"],
                created_at=created_dt,
            )
        )
    return items


@router.put("/me/keys/{provider}")
async def save_user_key(
    provider: str,
    req: SaveKeyRequest,
    user: AuthUser = Depends(get_current_user),
):
    """Save an encrypted API key for a provider. Key capped to 512 chars; never logged."""
    try:
        prov = validate_provider(provider)
    except ValueError as ve:
        raise HTTPException(status_code=400, detail=str(ve))

    if not _check_user_key_save_rate_limit(user.id):
        raise HTTPException(
            status_code=429,
            detail="Rate limit exceeded. You can save at most 10 API keys per minute.",
        )

    try:
        encrypted_key, last4 = encrypt_key(req.api_key)
    except ValueError as ve:
        raise HTTPException(status_code=400, detail=str(ve))
    finally:
        # Clear plaintext request body from scope
        req.api_key = ""

    success = db.save_user_key_db(user.id, prov, encrypted_key, last4)
    if not success:
        raise HTTPException(status_code=500, detail="Failed to save encrypted API key.")

    return {"ok": True, "provider": prov, "last4": last4}


@router.delete("/me/keys/{provider}")
async def delete_user_key(
    provider: str,
    user: AuthUser = Depends(get_current_user),
):
    """Delete a saved API key for a provider."""
    try:
        prov = validate_provider(provider)
    except ValueError as ve:
        raise HTTPException(status_code=400, detail=str(ve))

    deleted = db.delete_user_key_db(user.id, prov)
    if not deleted:
        raise HTTPException(status_code=500, detail="Failed to delete saved API key.")
    return {"ok": True, "provider": prov}


# ---------------------------------------------------------------------------
# BYOK LLM Test Endpoint
# ---------------------------------------------------------------------------

@router.post("/llm/test", response_model=LLMTestResponse)
async def test_llm_connection(
    request: Request,
    user: Optional[AuthUser] = Depends(get_optional_user),
    x_llm_provider: Optional[str] = Header(None, alias="X-LLM-Provider"),
    x_llm_model: Optional[str] = Header(None, alias="X-LLM-Model"),
    x_llm_key: Optional[str] = Header(None, alias="X-LLM-Key"),
):
    """
    Test connectivity to an LLM provider using a ~16 token probe.
    Rate-limited in-memory per client IP (10 requests/minute).
    """
    client_ip = _get_client_ip(request)
    if not check_ip_rate_limit(client_ip):
        raise HTTPException(
            status_code=429,
            detail="Rate limit exceeded. Please wait a minute before testing again.",
        )

    selection = _resolve_selection("test", x_llm_provider, x_llm_model, x_llm_key, user=user)
    prov = selection.provider if selection else "groq"
    mod = (
        selection.model
        if (selection and selection.model)
        else PROVIDER_REGISTRY[prov]["default_models"]["test"]
    )

    raw_key = (
        selection.api_key.get_secret_value()
        if (selection and selection.api_key)
        else None
    )
    keys_to_scrub = [raw_key] if raw_key else []

    try:
        try:
            llm = get_llm("test", selection)
            await run_in_threadpool(llm.invoke, [{"role": "user", "content": "Hi"}])
        except Exception as first_exc:
            err_str = str(first_exc).lower()
            if any(k in err_str for k in ("temperature", "max_tokens", "parameter", "unsupported", "extra_forbidden")):
                retry_llm = get_llm(
                    "test",
                    selection,
                    override_options={"omit_temperature": True, "max_completion_tokens": 16, "max_tokens": 16},
                )
                await run_in_threadpool(retry_llm.invoke, [{"role": "user", "content": "Hi"}])
            else:
                raise first_exc

        return LLMTestResponse(ok=True, provider=prov, model=mod, error=None)
    except Exception as exc:
        scrubbed = scrub_exception_chain(exc, keys=keys_to_scrub)
        return LLMTestResponse(ok=False, provider=prov, model=mod, error=scrubbed)
