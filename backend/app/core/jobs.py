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


# ---------------------------------------------------------------------------
# Thread-safe in-memory store
# ---------------------------------------------------------------------------

_lock = threading.Lock()
_jobs: Dict[str, JobRecord] = {}


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
