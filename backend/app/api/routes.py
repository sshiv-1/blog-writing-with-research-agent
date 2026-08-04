from __future__ import annotations

from fastapi import APIRouter, BackgroundTasks, HTTPException

from ..core.agent import generate_blog
from ..core.jobs import create_job, get_job
from ..models.schemas import BlogResult, GenerateRequest, JobStatusResponse

router = APIRouter()


@router.post("/generate", response_model=JobStatusResponse, status_code=202)
async def start_generation(req: GenerateRequest, background_tasks: BackgroundTasks):
    """
    Start a blog generation job.
    Returns immediately with a job_id; generation runs in the background.
    Poll GET /jobs/{job_id} for progress.
    """
    record = create_job()
    background_tasks.add_task(
        generate_blog,
        job_id=record.job_id,
        topic=req.topic,
        tone=req.tone,
        length=req.length,
        style=req.style,
        audience=req.audience,
        use_web=req.use_web,
    )
    return JobStatusResponse(
        job_id=record.job_id,
        status="queued",
        stage="queued",
        progress=0,
    )


@router.get("/jobs/{job_id}", response_model=JobStatusResponse)
async def get_job_status(job_id: str):
    """Poll the progress of a generation job."""
    record = get_job(job_id)
    if record is None:
        raise HTTPException(status_code=404, detail="Job not found")
    return JobStatusResponse(
        job_id=record.job_id,
        status=record.status,
        stage=record.stage,
        progress=record.progress,
        error=record.error,
    )


@router.get("/jobs/{job_id}/result", response_model=BlogResult)
async def get_job_result(job_id: str):
    """
    Fetch the final blog output.
    Returns 409 if the job is not yet complete.
    """
    record = get_job(job_id)
    if record is None:
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
