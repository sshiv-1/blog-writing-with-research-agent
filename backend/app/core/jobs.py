from __future__ import annotations

import threading
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, Literal, Optional


@dataclass
class JobRecord:
    job_id: str
    status: str = "queued"    # queued | running | done | error
    stage: str = "queued"     # queued | routing | researching | planning | writing | finalizing | done
    progress: int = 0         # 0-100
    result: Optional[Dict[str, Any]] = None
    error: Optional[str] = None
    created_at: datetime = field(default_factory=datetime.utcnow)


@dataclass
class SlideJobRecord:
    job_id: str
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


def create_job() -> JobRecord:
    """Create a new job and return its record."""
    job_id = str(uuid.uuid4())
    record = JobRecord(job_id=job_id)
    with _lock:
        _jobs[job_id] = record
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
    """Partially update a job record. Only non-None kwargs are applied."""
    with _lock:
        rec = _jobs.get(job_id)
        if rec is None:
            return
        if status is not None:
            rec.status = status
        if stage is not None:
            rec.stage = stage
        if progress is not None:
            rec.progress = progress
        if result is not None:
            rec.result = result
        if error is not None:
            rec.error = error


def get_job(job_id: str) -> Optional[JobRecord]:
    """Return the job record or None if not found."""
    with _lock:
        return _jobs.get(job_id)


def create_slide_job(job_id: str) -> SlideJobRecord:
    """Create or reset a slide job associated with a blog job_id."""
    record = SlideJobRecord(job_id=job_id)
    with _lock:
        _slide_jobs[job_id] = record
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
    """Partially update a slide job record."""
    with _lock:
        rec = _slide_jobs.get(job_id)
        if rec is None:
            return
        if status is not None:
            rec.status = status
        if stage is not None:
            rec.stage = stage
        if progress is not None:
            rec.progress = progress
        if slide_count is not None:
            rec.slide_count = slide_count
        if warnings is not None:
            rec.warnings = warnings
        if error is not None:
            rec.error = error
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


def get_slide_job(job_id: str) -> Optional[SlideJobRecord]:
    """Return the slide job record or None if not found."""
    with _lock:
        return _slide_jobs.get(job_id)

