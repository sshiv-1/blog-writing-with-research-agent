from __future__ import annotations

import logging
import re
import threading
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, Literal, Optional

from . import db
from .llm import scrub_exception_chain

logger = logging.getLogger("app.core.jobs")


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
    created_at: datetime = field(default_factory=datetime.utcnow)


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
    created_at: datetime = field(default_factory=datetime.utcnow)


# ---------------------------------------------------------------------------
# Thread-safe in-memory store
# ---------------------------------------------------------------------------

_lock = threading.Lock()
_jobs: Dict[str, JobRecord] = {}
_slide_jobs: Dict[str, SlideJobRecord] = {}


def _run_in_background(func, *args, **kwargs) -> None:
    """Run a database or storage operation on a daemon thread without blocking the caller."""
    def _worker():
        try:
            func(*args, **kwargs)
        except Exception as exc:
            logger.warning("Background DB/storage task failed: %s", scrub_exception_chain(exc))

    t = threading.Thread(target=_worker, daemon=True)
    t.start()


def create_job(
    *,
    user_id: Optional[str] = None,
    topic: Optional[str] = None,
    params: Optional[Dict[str, Any]] = None,
) -> JobRecord:
    """Create a new blog job and return its record, scheduling DB write-through if authenticated."""
    job_id = str(uuid.uuid4())
    record = JobRecord(
        job_id=job_id,
        user_id=user_id,
        topic=topic,
        params=params,
    )
    with _lock:
        _jobs[job_id] = record

    if user_id:
        _run_in_background(
            db.save_job_db,
            job_id=record.job_id,
            user_id=record.user_id,
            topic=record.topic,
            status=record.status,
            stage=record.stage,
            progress=record.progress,
            params=record.params,
            result=record.result,
            error=record.error,
        )

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

        user_id = rec.user_id
        topic = rec.topic
        curr_status = rec.status
        curr_stage = rec.stage
        curr_prog = rec.progress
        curr_params = rec.params
        curr_result = rec.result
        curr_error = rec.error

    if should_persist and user_id:
        _run_in_background(
            db.save_job_db,
            job_id=job_id,
            user_id=user_id,
            topic=topic,
            status=curr_status,
            stage=curr_stage,
            progress=curr_prog,
            params=curr_params,
            result=curr_result,
            error=curr_error,
        )


def get_job(job_id: str) -> Optional[JobRecord]:
    """Return the job record from in-memory cache, falling back to Supabase DB on cache miss."""
    with _lock:
        rec = _jobs.get(job_id)
        if rec is not None:
            return rec

    # Fallback to Supabase
    db_row = db.get_job_db(job_id)
    if db_row is None:
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
        created_at=db._parse_iso_datetime(db_row.get("created_at")) or datetime.utcnow(),
    )

    with _lock:
        _jobs[job_id] = record
    return record


def create_slide_job(job_id: str, user_id: Optional[str] = None) -> SlideJobRecord:
    """Create or reset a slide job associated with a blog job_id."""
    record = SlideJobRecord(job_id=job_id, user_id=user_id)
    with _lock:
        _slide_jobs[job_id] = record

    if user_id:
        _run_in_background(
            db.save_slide_job_db,
            job_id=job_id,
            user_id=user_id,
            status=record.status,
            stage=record.stage,
            progress=record.progress,
            slide_count=record.slide_count,
            warnings=record.warnings,
            deck=record.deck,
            title=record.title,
            error=record.error,
        )

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
    with _lock:
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

        user_id = rec.user_id
        curr_status = rec.status
        curr_stage = rec.stage
        curr_prog = rec.progress
        curr_count = rec.slide_count
        curr_warn = rec.warnings
        curr_deck = rec.deck
        curr_title = rec.title
        curr_error = rec.error
        curr_pdf = rec.pdf_bytes
        curr_pptx = rec.pptx_bytes
        curr_tex = rec.tex_content

    if should_persist and user_id:
        _run_in_background(
            db.save_slide_job_db,
            job_id=job_id,
            user_id=user_id,
            status=curr_status,
            stage=curr_stage,
            progress=curr_prog,
            slide_count=curr_count,
            warnings=curr_warn,
            deck=curr_deck,
            title=curr_title,
            error=curr_error,
        )

        # Upload artifacts to Supabase storage on completion
        if curr_status == "done":
            safe_title = re.sub(r"[^\w\-_]+", "_", curr_title).strip("_") or "slides"
            if curr_pdf:
                _run_in_background(
                    db.upload_artifact_storage,
                    user_id=user_id,
                    job_id=job_id,
                    filename=f"{safe_title}.pdf",
                    content=curr_pdf,
                    content_type="application/pdf",
                )
            if curr_pptx:
                _run_in_background(
                    db.upload_artifact_storage,
                    user_id=user_id,
                    job_id=job_id,
                    filename=f"{safe_title}.pptx",
                    content=curr_pptx,
                    content_type="application/vnd.openxmlformats-officedocument.presentationml.presentation",
                )
            if curr_tex:
                _run_in_background(
                    db.upload_artifact_storage,
                    user_id=user_id,
                    job_id=job_id,
                    filename=f"{safe_title}.tex",
                    content=curr_tex.encode("utf-8"),
                    content_type="text/x-tex",
                )


def get_slide_job(job_id: str) -> Optional[SlideJobRecord]:
    """Return the slide job record from in-memory cache, falling back to DB on miss."""
    with _lock:
        rec = _slide_jobs.get(job_id)
        if rec is not None:
            return rec

    # Fallback to Supabase
    db_row = db.get_slide_job_db(job_id)
    if db_row is None:
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
        created_at=db._parse_iso_datetime(db_row.get("created_at")) or datetime.utcnow(),
    )

    with _lock:
        _slide_jobs[job_id] = record
    return record


def delete_job_record(job_id: str, user_id: Optional[str] = None) -> bool:
    """Delete job and associated slide job from memory and database."""
    with _lock:
        _jobs.pop(job_id, None)
        _slide_jobs.pop(job_id, None)

    return db.delete_job_db(job_id, user_id)
