from __future__ import annotations

import logging
import re
import threading
import time
import uuid
from collections import OrderedDict, deque
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, Optional

from . import db
from .llm import scrub_exception_chain

logger = logging.getLogger("app.core.jobs")

MAX_CACHED_JOBS = 200
JOB_CACHE_TTL_SECONDS = 3600.0
STALE_JOB_SECONDS = 900.0
MAX_DELETED_TOMBSTONES = 10000


class JobCancelledError(Exception):
    """Raised when an active background job is cancelled or deleted."""


@dataclass
class JobRecord:
    job_id: str
    user_id: Optional[str] = None
    topic: Optional[str] = None
    status: str = "queued"    # queued | running | done | error
    stage: str = "queued"     # queued | routing | researching | planning | writing | finalizing | done
    progress: int = 0         # 0-100
    params: Optional[Dict[str, Any]] = None
    result: Optional[Dict[str, Any]] = None
    error: Optional[str] = None
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    updated_monotonic: float = field(default_factory=time.monotonic)


@dataclass
class SlideJobRecord:
    job_id: str
    user_id: Optional[str] = None
    status: str = "queued"    # queued | running | done | error
    stage: str = "queued"     # queued | planning | writing_latex | compiling | done
    progress: int = 0         # 0-100
    slide_count: Optional[int] = None
    warnings: list[str] = field(default_factory=list)
    error: Optional[str] = None
    pdf_bytes: Optional[bytes] = None
    pptx_bytes: Optional[bytes] = None
    tex_content: Optional[str] = None
    title: str = "slides"
    deck: Optional[Dict[str, Any]] = None
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    updated_monotonic: float = field(default_factory=time.monotonic)


# ---------------------------------------------------------------------------
# Thread-safe bounded in-memory stores, per-job I/O locks & tombstones
# ---------------------------------------------------------------------------

_lock = threading.Lock()
_jobs: OrderedDict[str, JobRecord] = OrderedDict()
_slide_jobs: OrderedDict[str, SlideJobRecord] = OrderedDict()
_deleted_jobs: OrderedDict[str, float] = OrderedDict()
_job_io_locks: dict[str, threading.Lock] = {}

# Authoritative per-user in-process task & daily creation tracking (survives DELETE races)
_active_user_tasks: dict[str, int] = {}
_daily_user_creations: dict[str, deque[float]] = {}


def _get_job_io_lock(job_id: str) -> threading.Lock:
    with _lock:
        if job_id not in _job_io_locks:
            if len(_job_io_locks) > MAX_DELETED_TOMBSTONES:
                # Prune locks for jobs no longer cached or active
                stale_keys = [k for k in _job_io_locks if k not in _jobs and k not in _slide_jobs]
                for k in stale_keys[: len(_job_io_locks) // 2]:
                    _job_io_locks.pop(k, None)
            _job_io_locks[job_id] = threading.Lock()
        return _job_io_locks[job_id]


def is_job_deleted(job_id: str) -> bool:
    """Return True if job_id has been deleted/cancelled."""
    with _lock:
        return job_id in _deleted_jobs


def _mark_job_deleted_locked(job_id: str) -> None:
    _deleted_jobs[job_id] = time.monotonic()
    _deleted_jobs.move_to_end(job_id)
    while len(_deleted_jobs) > MAX_DELETED_TOMBSTONES:
        _deleted_jobs.popitem(last=False)


def _evict_cache_locked(cache: OrderedDict[str, Any]) -> None:
    now = time.monotonic()
    expired_keys = [
        k
        for k, rec in cache.items()
        if rec.status in ("done", "error") and (now - rec.updated_monotonic) > JOB_CACHE_TTL_SECONDS
    ]
    for k in expired_keys:
        cache.pop(k, None)

    if len(cache) <= MAX_CACHED_JOBS:
        return

    for k in list(cache.keys()):
        if len(cache) <= MAX_CACHED_JOBS:
            break
        rec = cache[k]
        if rec.status in ("done", "error"):
            cache.pop(k, None)


def _check_memory_staleness(rec: JobRecord | SlideJobRecord) -> None:
    if rec.status in ("queued", "running") and (time.monotonic() - rec.updated_monotonic) > STALE_JOB_SECONDS:
        rec.status = "error"
        rec.error = "Interrupted by a server restart"


def _run_in_background(func, *args, **kwargs) -> None:
    """Run a database or storage operation on a daemon thread without blocking the caller."""
    def _worker():
        try:
            func(*args, **kwargs)
        except Exception as exc:
            logger.warning("Background DB/storage task failed: %s", scrub_exception_chain(exc))

    t = threading.Thread(target=_worker, daemon=True)
    t.start()


def safe_ascii_title(raw_title: Optional[str]) -> str:
    """Sanitize a deck title into a safe ASCII filename stem."""
    cleaned = re.sub(r"[^A-Za-z0-9\-_]+", "_", raw_title or "slides").strip("_")[:80]
    return cleaned or "slides"


# ---------------------------------------------------------------------------
# Per-User Active Task & Daily Quota Tracking
# ---------------------------------------------------------------------------

def register_user_task_start(user_id: Optional[str]) -> None:
    """Record an in-flight background job execution and daily creation for a user."""
    if not user_id:
        return
    now = time.time()
    cutoff = now - 86400.0
    with _lock:
        _active_user_tasks[user_id] = _active_user_tasks.get(user_id, 0) + 1
        dq = _daily_user_creations.setdefault(user_id, deque())
        while dq and dq[0] <= cutoff:
            dq.popleft()
        dq.append(now)


def register_user_task_end(user_id: Optional[str]) -> None:
    """Decrement active background task counter when a job finishes or errors."""
    if not user_id:
        return
    with _lock:
        curr = _active_user_tasks.get(user_id, 0)
        if curr <= 1:
            _active_user_tasks.pop(user_id, None)
        else:
            _active_user_tasks[user_id] = curr - 1


def get_user_memory_quota_counts(user_id: str) -> tuple[int, int]:
    """Return (active_in_flight_tasks, daily_creations_last_24h) for user_id."""
    now = time.time()
    cutoff = now - 86400.0
    with _lock:
        active = _active_user_tasks.get(user_id, 0)
        dq = _daily_user_creations.get(user_id)
        if dq is not None:
            while dq and dq[0] <= cutoff:
                dq.popleft()
            daily = len(dq)
            if not dq:
                _daily_user_creations.pop(user_id, None)
        else:
            daily = 0
        return active, daily


# ---------------------------------------------------------------------------
# Serialized DB & Storage Sync Helpers
# ---------------------------------------------------------------------------

def _sync_blog_job_to_db(job_id: str) -> None:
    io_lock = _get_job_io_lock(job_id)
    with io_lock:
        if is_job_deleted(job_id):
            return
        with _lock:
            rec = _jobs.get(job_id)
            if rec is None or not rec.user_id:
                return
            snapshot = {
                "job_id": rec.job_id,
                "user_id": rec.user_id,
                "topic": rec.topic,
                "status": rec.status,
                "stage": rec.stage,
                "progress": rec.progress,
                "params": rec.params,
                "result": rec.result,
                "error": rec.error,
            }
        db.save_job_db(**snapshot)


def _sync_slide_job_to_db(job_id: str, upload_artifacts: bool = False) -> None:
    io_lock = _get_job_io_lock(job_id)
    with io_lock:
        if is_job_deleted(job_id):
            return
        with _lock:
            rec = _slide_jobs.get(job_id)
            if rec is None or not rec.user_id:
                return
            snapshot = {
                "job_id": rec.job_id,
                "user_id": rec.user_id,
                "status": rec.status,
                "stage": rec.stage,
                "progress": rec.progress,
                "slide_count": rec.slide_count,
                "warnings": list(rec.warnings),
                "deck": rec.deck,
                "title": rec.title,
                "error": rec.error,
            }
            curr_status = rec.status
            curr_pdf = rec.pdf_bytes
            curr_pptx = rec.pptx_bytes
            curr_tex = rec.tex_content
            user_id = rec.user_id
            safe_title = safe_ascii_title(rec.title)

        db.save_slide_job_db(**snapshot)

        if upload_artifacts and curr_status == "done" and db.is_configured():
            pdf_ok = False
            pptx_ok = False
            tex_ok = False
            if curr_pdf and not is_job_deleted(job_id):
                pdf_ok = db.upload_artifact_storage(
                    user_id=user_id,
                    job_id=job_id,
                    filename=f"{safe_title}.pdf",
                    content=curr_pdf,
                    content_type="application/pdf",
                )
            if curr_pptx and not is_job_deleted(job_id):
                pptx_ok = db.upload_artifact_storage(
                    user_id=user_id,
                    job_id=job_id,
                    filename=f"{safe_title}.pptx",
                    content=curr_pptx,
                    content_type="application/vnd.openxmlformats-officedocument.presentationml.presentation",
                )
            if curr_tex and not is_job_deleted(job_id):
                tex_ok = db.upload_artifact_storage(
                    user_id=user_id,
                    job_id=job_id,
                    filename=f"{safe_title}.tex",
                    content=curr_tex.encode("utf-8"),
                    content_type="text/x-tex",
                )
            # Free large binary payloads from in-memory dict once persisted to private Storage
            with _lock:
                live = _slide_jobs.get(job_id)
                if live is not None:
                    if pdf_ok and live.pdf_bytes is curr_pdf:
                        live.pdf_bytes = None
                    if pptx_ok and live.pptx_bytes is curr_pptx:
                        live.pptx_bytes = None
                    if tex_ok and live.tex_content is curr_tex:
                        live.tex_content = None


# ---------------------------------------------------------------------------
# Blog Job CRUD
# ---------------------------------------------------------------------------

def create_job(
    *,
    user_id: Optional[str] = None,
    topic: Optional[str] = None,
    params: Optional[Dict[str, Any]] = None,
) -> JobRecord:
    """Create a new blog job and return its record, scheduling serialized DB write-through if authenticated."""
    job_id = str(uuid.uuid4())
    record = JobRecord(
        job_id=job_id,
        user_id=user_id,
        topic=topic,
        params=params,
    )
    with _lock:
        _evict_cache_locked(_jobs)
        _jobs[job_id] = record
        _jobs.move_to_end(job_id)

    if user_id:
        _run_in_background(_sync_blog_job_to_db, job_id)

    return record


def update_job(
    job_id: str,
    *,
    status: Optional[str] = None,
    stage: Optional[str] = None,
    progress: Optional[int] = None,
    result: Optional[Dict[str, Any]] = None,
    error: Optional[str] = None,
) -> None:
    """
    Partially update a job record.
    Writes through to Supabase ONLY on stage changes or terminal states (done/error),
    never on every progress tick.
    """
    should_persist = False
    with _lock:
        if job_id in _deleted_jobs:
            return
        rec = _jobs.get(job_id)
        if rec is None:
            return

        if stage is not None and stage != rec.stage:
            rec.stage = stage
            should_persist = True
        if status is not None and status != rec.status:
            rec.status = status
            if status in ("done", "error"):
                should_persist = True
        if progress is not None:
            rec.progress = progress
        if result is not None:
            rec.result = result
            should_persist = True
        if error is not None:
            rec.error = error
            should_persist = True

        rec.updated_monotonic = time.monotonic()
        _jobs.move_to_end(job_id)
        user_id = rec.user_id

    if should_persist and user_id:
        _run_in_background(_sync_blog_job_to_db, job_id)


def get_job(job_id: str) -> Optional[JobRecord]:
    """Return the job record from in-memory cache, falling back to Supabase DB on cache miss."""
    with _lock:
        if job_id in _deleted_jobs:
            return None
        rec = _jobs.get(job_id)
        if rec is not None:
            _check_memory_staleness(rec)
            _jobs.move_to_end(job_id)
            return rec

    # Fallback to Supabase
    db_row = db.get_job_db(job_id)
    if db_row is None or is_job_deleted(job_id):
        return None

    state = db_row.get("state") or {}
    record = JobRecord(
        job_id=db_row["id"],
        user_id=db_row.get("user_id"),
        topic=db_row.get("topic"),
        status=db_row.get("status", "queued"),
        stage=db_row.get("stage", "queued"),
        progress=db_row.get("progress", 0),
        params=db_row.get("params"),
        result=state.get("result"),
        error=db_row.get("error"),
        created_at=db._parse_iso_datetime(db_row.get("created_at")) or datetime.now(timezone.utc),
    )

    with _lock:
        if job_id in _deleted_jobs:
            return None
        _evict_cache_locked(_jobs)
        _jobs[job_id] = record
        _jobs.move_to_end(job_id)
    return record


# ---------------------------------------------------------------------------
# Slide Job CRUD
# ---------------------------------------------------------------------------

def create_slide_job(job_id: str, user_id: Optional[str] = None) -> SlideJobRecord:
    """Create or reset a slide job associated with a blog job_id."""
    record = SlideJobRecord(job_id=job_id, user_id=user_id)
    with _lock:
        _evict_cache_locked(_slide_jobs)
        _slide_jobs[job_id] = record
        _slide_jobs.move_to_end(job_id)

    if user_id:
        _run_in_background(_sync_slide_job_to_db, job_id, False)

    return record


def update_slide_job(
    job_id: str,
    *,
    status: Optional[str] = None,
    stage: Optional[str] = None,
    progress: Optional[int] = None,
    slide_count: Optional[int] = None,
    warnings: Optional[list[str]] = None,
    error: Optional[str] = None,
    pdf_bytes: Optional[bytes] = None,
    pptx_bytes: Optional[bytes] = None,
    tex_content: Optional[str] = None,
    title: Optional[str] = None,
    deck: Optional[Dict[str, Any]] = None,
) -> None:
    """Partially update a slide job record with write-through on stage changes or done/error."""
    should_persist = False
    should_upload = False
    with _lock:
        if job_id in _deleted_jobs:
            return
        rec = _slide_jobs.get(job_id)
        if rec is None:
            return

        if stage is not None and stage != rec.stage:
            rec.stage = stage
            should_persist = True
        if status is not None and status != rec.status:
            rec.status = status
            if status in ("done", "error"):
                should_persist = True
        if progress is not None:
            rec.progress = progress
        if slide_count is not None:
            rec.slide_count = slide_count
        if warnings is not None:
            rec.warnings = warnings
        if error is not None:
            rec.error = error
            should_persist = True
        if pdf_bytes is not None:
            rec.pdf_bytes = pdf_bytes
        if pptx_bytes is not None:
            rec.pptx_bytes = pptx_bytes
        if tex_content is not None:
            rec.tex_content = tex_content
        if title is not None:
            rec.title = title
        if deck is not None:
            rec.deck = deck

        rec.updated_monotonic = time.monotonic()
        _slide_jobs.move_to_end(job_id)
        user_id = rec.user_id
        should_upload = (rec.status == "done")

    if should_persist and user_id:
        _run_in_background(_sync_slide_job_to_db, job_id, should_upload)


def get_slide_job(job_id: str) -> Optional[SlideJobRecord]:
    """Return the slide job record from in-memory cache, falling back to DB on miss."""
    with _lock:
        if job_id in _deleted_jobs:
            return None
        rec = _slide_jobs.get(job_id)
        if rec is not None:
            _check_memory_staleness(rec)
            _slide_jobs.move_to_end(job_id)
            return rec

    # Fallback to Supabase
    db_row = db.get_slide_job_db(job_id)
    if db_row is None or is_job_deleted(job_id):
        return None

    result_data = db_row.get("result") or {}
    record = SlideJobRecord(
        job_id=db_row["id"],
        user_id=db_row.get("user_id"),
        status=db_row.get("status", "queued"),
        stage=db_row.get("current_step", "queued"),
        progress=db_row.get("progress", 0),
        slide_count=result_data.get("slide_count"),
        warnings=result_data.get("warnings") or [],
        deck=result_data.get("deck"),
        title=result_data.get("title", "slides"),
        error=db_row.get("error"),
        created_at=db._parse_iso_datetime(db_row.get("created_at")) or datetime.now(timezone.utc),
    )

    with _lock:
        if job_id in _deleted_jobs:
            return None
        _evict_cache_locked(_slide_jobs)
        _slide_jobs[job_id] = record
        _slide_jobs.move_to_end(job_id)
    return record


def delete_job_record(job_id: str, user_id: Optional[str] = None) -> bool:
    """Tombstone and delete job and associated slide job from memory, DB, and Storage."""
    with _lock:
        _mark_job_deleted_locked(job_id)
        _jobs.pop(job_id, None)
        _slide_jobs.pop(job_id, None)

    io_lock = _get_job_io_lock(job_id)
    with io_lock:
        ok = db.delete_job_db(job_id, user_id)

    with _lock:
        _job_io_locks.pop(job_id, None)
    return ok
