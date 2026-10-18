from __future__ import annotations

import logging
import os
import threading
from datetime import datetime, timezone, timedelta
from typing import Any, Dict, List, Optional, Tuple

from .llm import scrub_exception_chain

logger = logging.getLogger("app.core.db")

_client_lock = threading.Lock()
_supabase_client = None
_warning_logged = False


def is_configured() -> bool:
    """Return True if both SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY are set."""
    url = os.getenv("SUPABASE_URL", "").strip()
    key = os.getenv("SUPABASE_SERVICE_ROLE_KEY", "").strip()
    return bool(url and key)


def get_supabase_client():
    """
    Return the singleton Supabase client, or None if unconfigured.
    Degrades gracefully to guest-only mode if credentials are missing.
    """
    global _supabase_client, _warning_logged
    if not is_configured():
        if not _warning_logged:
            logger.warning("SUPABASE_URL or SUPABASE_SERVICE_ROLE_KEY unset. Running in GUEST-ONLY in-memory mode.")
            _warning_logged = True
        return None

    if _supabase_client is None:
        with _client_lock:
            if _supabase_client is None:
                try:
                    from supabase import create_client
                    url = os.getenv("SUPABASE_URL", "").strip()
                    key = os.getenv("SUPABASE_SERVICE_ROLE_KEY", "").strip()
                    _supabase_client = create_client(url, key)
                    logger.info("Supabase client initialized successfully.")
                except Exception as exc:
                    logger.error("Failed to initialize Supabase client: %s", scrub_exception_chain(exc))
                    return None
    return _supabase_client


def _parse_iso_datetime(dt_str: Optional[str]) -> Optional[datetime]:
    if not dt_str:
        return None
    try:
        # Normalize trailing Z to +00:00 for fromisoformat
        clean = dt_str.replace("Z", "+00:00")
        return datetime.fromisoformat(clean)
    except Exception:
        return None


def cleanup_stale_jobs_on_startup() -> None:
    """
    At startup, mark any DB jobs in 'queued' or 'running' status older than
    15 minutes as failed with error 'Interrupted by a server restart'.
    """
    client = get_supabase_client()
    if client is None:
        return

    cutoff = (datetime.now(timezone.utc) - timedelta(minutes=15)).isoformat()
    now_iso = datetime.now(timezone.utc).isoformat()
    stale_error = "Interrupted by a server restart"

    try:
        # Clean stale blog jobs
        client.table("jobs").update({
            "status": "error",
            "error": stale_error,
            "updated_at": now_iso,
        }).in_("status", ["queued", "running"]).lt("updated_at", cutoff).execute()

        # Clean stale slide jobs
        client.table("slide_jobs").update({
            "status": "error",
            "error": stale_error,
            "updated_at": now_iso,
        }).in_("status", ["queued", "running"]).lt("updated_at", cutoff).execute()
        logger.info("Stale job cleanup on startup completed.")
    except Exception as exc:
        logger.warning("Failed to clean up stale jobs on startup: %s", scrub_exception_chain(exc))


def check_and_mark_stale_job(row: dict, table_name: str = "jobs") -> dict:
    """
    When reading a DB job, if status is queued or running and updated_at is > 15m ago,
    mark it failed in-memory and update DB in background.
    """
    status = row.get("status")
    if status in ("queued", "running"):
        updated_at = _parse_iso_datetime(row.get("updated_at") or row.get("created_at"))
        if updated_at:
            now = datetime.now(timezone.utc)
            if updated_at.tzinfo is None:
                updated_at = updated_at.replace(tzinfo=timezone.utc)
            if (now - updated_at) > timedelta(minutes=15):
                row["status"] = "error"
                row["error"] = "Interrupted by a server restart"
                # Persist stale update to DB
                client = get_supabase_client()
                if client is not None:
                    job_id = row.get("id")
                    threading.Thread(
                        target=lambda: _safe_update_stale_db(client, table_name, job_id, row["error"]),
                        daemon=True,
                    ).start()
    return row


def _safe_update_stale_db(client, table_name: str, job_id: str, error: str) -> None:
    try:
        now_iso = datetime.now(timezone.utc).isoformat()
        client.table(table_name).update({
            "status": "error",
            "error": error,
            "updated_at": now_iso,
        }).eq("id", job_id).execute()
    except Exception as exc:
        logger.warning("Failed to update stale job %s in DB: %s", job_id, scrub_exception_chain(exc))


# ---------------------------------------------------------------------------
# Blog Jobs DB Operations
# ---------------------------------------------------------------------------

def save_job_db(
    job_id: str,
    user_id: Optional[str],
    topic: Optional[str],
    status: str,
    stage: str,
    progress: int,
    params: Optional[Dict[str, Any]],
    result: Optional[Dict[str, Any]],
    error: Optional[str],
) -> None:
    """Upsert blog job into Supabase jobs table."""
    client = get_supabase_client()
    if client is None or not user_id:
        return

    now_iso = datetime.now(timezone.utc).isoformat()
    record = {
        "id": job_id,
        "user_id": user_id,
        "topic": topic or "",
        "status": status,
        "stage": stage,
        "progress": progress,
        "params": params or {},
        "state": {"stage": stage, "progress": progress, "result": result},
        "error": error,
        "updated_at": now_iso,
    }

    try:
        client.table("jobs").upsert(record).execute()
    except Exception as exc:
        logger.warning("Supabase save_job failed for %s: %s", job_id, scrub_exception_chain(exc))


def get_job_db(job_id: str) -> Optional[dict]:
    """Fetch blog job from Supabase by ID, checking staleness."""
    client = get_supabase_client()
    if client is None:
        return None

    try:
        resp = client.table("jobs").select("*").eq("id", job_id).maybe_single().execute()
        if resp and resp.data:
            return check_and_mark_stale_job(resp.data, "jobs")
        return None
    except Exception as exc:
        logger.warning("Supabase get_job failed for %s: %s", job_id, scrub_exception_chain(exc))
        return None


def list_user_jobs_db(user_id: str, limit: int = 20, offset: int = 0) -> Tuple[List[dict], int]:
    """
    Return paginated list of jobs for a user sorted by created_at desc,
    along with total count and has_slides flag.
    """
    client = get_supabase_client()
    if client is None or not user_id:
        return [], 0

    try:
        # Total count
        count_resp = client.table("jobs").select("id", count="exact").eq("user_id", user_id).execute()
        total = count_resp.count if count_resp.count is not None else 0

        # Paginated rows
        resp = (
            client.table("jobs")
            .select("*")
            .eq("user_id", user_id)
            .order("created_at", desc=True)
            .range(offset, offset + limit - 1)
            .execute()
        )
        rows = resp.data or []

        # Find which jobs have slides
        if rows:
            job_ids = [r["id"] for r in rows]
            slide_resp = client.table("slide_jobs").select("id").in_("id", job_ids).execute()
            slide_ids = {s["id"] for s in (slide_resp.data or [])}
            for r in rows:
                r["has_slides"] = r["id"] in slide_ids
                check_and_mark_stale_job(r, "jobs")
        return rows, total
    except Exception as exc:
        logger.warning("Supabase list_user_jobs failed for %s: %s", user_id, scrub_exception_chain(exc))
        return [], 0


def count_user_active_jobs_db(user_id: str) -> int:
    """Count active (queued or running) jobs for a user across jobs and slide_jobs."""
    client = get_supabase_client()
    if client is None or not user_id:
        return 0

    try:
        resp = (
            client.table("jobs")
            .select("id", count="exact")
            .eq("user_id", user_id)
            .in_("status", ["queued", "running"])
            .execute()
        )
        return resp.count if resp.count is not None else 0
    except Exception as exc:
        logger.warning("Supabase count_user_active_jobs failed: %s", scrub_exception_chain(exc))
        return 0


def count_user_daily_jobs_db(user_id: str) -> int:
    """Count jobs created by user in the last 24 hours."""
    client = get_supabase_client()
    if client is None or not user_id:
        return 0

    try:
        cutoff = (datetime.now(timezone.utc) - timedelta(hours=24)).isoformat()
        resp = (
            client.table("jobs")
            .select("id", count="exact")
            .eq("user_id", user_id)
            .gte("created_at", cutoff)
            .execute()
        )
        return resp.count if resp.count is not None else 0
    except Exception as exc:
        logger.warning("Supabase count_user_daily_jobs failed: %s", scrub_exception_chain(exc))
        return 0


def delete_job_db(job_id: str, user_id: Optional[str]) -> bool:
    """Delete job, cascading to slide_jobs, and remove artifacts from storage."""
    client = get_supabase_client()
    if client is None:
        return True

    try:
        query = client.table("jobs").delete().eq("id", job_id)
        if user_id:
            query = query.eq("user_id", user_id)
        query.execute()

        # Clean artifacts from private storage bucket
        if user_id:
            try:
                prefix = f"{user_id}/{job_id}"
                files = client.storage.from_("artifacts").list(prefix)
                if files:
                    file_paths = [f"{prefix}/{f['name']}" for f in files]
                    client.storage.from_("artifacts").remove(file_paths)
            except Exception as store_exc:
                logger.warning("Failed to clean up storage artifacts for %s: %s", job_id, scrub_exception_chain(store_exc))
        return True
    except Exception as exc:
        logger.warning("Supabase delete_job failed for %s: %s", job_id, scrub_exception_chain(exc))
        return False


# ---------------------------------------------------------------------------
# Slide Jobs DB Operations
# ---------------------------------------------------------------------------

def save_slide_job_db(
    job_id: str,
    user_id: Optional[str],
    status: str,
    stage: str,
    progress: int,
    slide_count: Optional[int],
    warnings: List[str],
    deck: Optional[Dict[str, Any]],
    title: str,
    error: Optional[str],
) -> None:
    """
    Upsert slide job into Supabase slide_jobs table.
    Stores slide_count, warnings, deck, and title inside the result jsonb.
    """
    client = get_supabase_client()
    if client is None or not user_id:
        return

    now_iso = datetime.now(timezone.utc).isoformat()
    result_data = {
        "slide_count": slide_count,
        "warnings": warnings or [],
        "deck": deck or {},
        "title": title or "slides",
    }

    record = {
        "id": job_id,
        "user_id": user_id,
        "status": status,
        "current_step": stage,
        "progress": progress,
        "error": error,
        "result": result_data,
        "updated_at": now_iso,
    }

    try:
        client.table("slide_jobs").upsert(record).execute()
    except Exception as exc:
        logger.warning("Supabase save_slide_job failed for %s: %s", job_id, scrub_exception_chain(exc))


def get_slide_job_db(job_id: str) -> Optional[dict]:
    """Fetch slide job from Supabase by ID, checking staleness."""
    client = get_supabase_client()
    if client is None:
        return None

    try:
        resp = client.table("slide_jobs").select("*").eq("id", job_id).maybe_single().execute()
        if resp and resp.data:
            return check_and_mark_stale_job(resp.data, "slide_jobs")
        return None
    except Exception as exc:
        logger.warning("Supabase get_slide_job failed for %s: %s", job_id, scrub_exception_chain(exc))
        return None


# ---------------------------------------------------------------------------
# User Saved API Keys Operations
# ---------------------------------------------------------------------------

def save_user_key_db(user_id: str, provider: str, encrypted_key: str, key_last4: str) -> bool:
    """Save an encrypted API key in user_api_keys table."""
    client = get_supabase_client()
    if client is None or not user_id:
        return False

    now_iso = datetime.now(timezone.utc).isoformat()
    record = {
        "user_id": user_id,
        "provider": provider,
        "encrypted_key": encrypted_key,
        "key_last4": key_last4,
        "created_at": now_iso,
    }

    try:
        client.table("user_api_keys").upsert(record).execute()
        return True
    except Exception as exc:
        logger.warning("Supabase save_user_key failed for user %s: %s", user_id, scrub_exception_chain(exc))
        return False


def get_user_key_db(user_id: str, provider: str) -> Optional[Tuple[str, str]]:
    """Return (encrypted_key, key_last4) or None."""
    client = get_supabase_client()
    if client is None or not user_id:
        return None

    try:
        resp = (
            client.table("user_api_keys")
            .select("encrypted_key, key_last4")
            .eq("user_id", user_id)
            .eq("provider", provider)
            .maybe_single()
            .execute()
        )
        if resp and resp.data:
            return resp.data["encrypted_key"], resp.data["key_last4"]
        return None
    except Exception as exc:
        logger.warning("Supabase get_user_key failed: %s", scrub_exception_chain(exc))
        return None


def list_user_keys_db(user_id: str) -> List[dict]:
    """Return list of saved keys: [{provider, last4, created_at}]. Never returns key bytes."""
    client = get_supabase_client()
    if client is None or not user_id:
        return []

    try:
        resp = (
            client.table("user_api_keys")
            .select("provider, key_last4, created_at")
            .eq("user_id", user_id)
            .order("created_at", desc=True)
            .execute()
        )
        rows = resp.data or []
        return [
            {
                "provider": r["provider"],
                "last4": r["key_last4"],
                "created_at": r.get("created_at"),
            }
            for r in rows
        ]
    except Exception as exc:
        logger.warning("Supabase list_user_keys failed: %s", scrub_exception_chain(exc))
        return []


def delete_user_key_db(user_id: str, provider: str) -> bool:
    """Delete a user's saved key for a specific provider."""
    client = get_supabase_client()
    if client is None or not user_id:
        return False

    try:
        client.table("user_api_keys").delete().eq("user_id", user_id).eq("provider", provider).execute()
        return True
    except Exception as exc:
        logger.warning("Supabase delete_user_key failed: %s", scrub_exception_chain(exc))
        return False


# ---------------------------------------------------------------------------
# Storage Artifact Operations (Private Bucket)
# ---------------------------------------------------------------------------

def upload_artifact_storage(
    user_id: str,
    job_id: str,
    filename: str,
    content: bytes,
    content_type: str,
) -> bool:
    """Upload artifact to private Supabase storage bucket under {user_id}/{job_id}/{filename}."""
    client = get_supabase_client()
    if client is None or not user_id:
        return False

    path = f"{user_id}/{job_id}/{filename}"
    try:
        # Use upsert option if supported or remove then upload
        client.storage.from_("artifacts").upload(
            path,
            content,
            file_options={"content-type": content_type, "upsert": "true"},
        )
        return True
    except Exception as exc:
        logger.warning("Supabase storage upload failed for %s: %s", path, scrub_exception_chain(exc))
        return False


def get_artifact_storage(user_id: str, job_id: str, filename: str) -> Optional[bytes]:
    """Download artifact bytes from private Supabase storage bucket."""
    client = get_supabase_client()
    if client is None or not user_id:
        return None

    path = f"{user_id}/{job_id}/{filename}"
    try:
        return client.storage.from_("artifacts").download(path)
    except Exception as exc:
        logger.warning("Supabase storage download failed for %s: %s", path, scrub_exception_chain(exc))
        return None
