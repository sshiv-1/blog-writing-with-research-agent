import re
from fastapi import APIRouter, BackgroundTasks, HTTPException, Query
from fastapi.responses import Response

from ..core.agent import generate_blog
from ..core.jobs import (
    create_job,
    create_slide_job,
    get_job,
    get_slide_job,
)
from ..core.slides import generate_slides_for_blog
from ..models.schemas import (
    BlogResult,
    GenerateRequest,
    GenerateSlidesRequest,
    JobStatusResponse,
    SlideJobStatusResponse,
)

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


# ---------------------------------------------------------------------------
# Slide Endpoints
# ---------------------------------------------------------------------------


@router.post("/jobs/{job_id}/slides", response_model=SlideJobStatusResponse, status_code=202)
async def start_slides_generation(
    job_id: str,
    req: GenerateSlidesRequest,
    background_tasks: BackgroundTasks,
):
    """
    Trigger slide generation from a completed blog job.
    Returns 409 if blog generation is not yet done.
    """
    blog_record = get_job(job_id)
    if blog_record is None:
        raise HTTPException(status_code=404, detail="Blog job not found")
    if blog_record.status != "done":
        raise HTTPException(
            status_code=409,
            detail=f"Blog job is not completed yet (status: {blog_record.status}, stage: {blog_record.stage})",
        )

    slide_job = create_slide_job(job_id)
    background_tasks.add_task(
        generate_slides_for_blog,
        job_id=job_id,
        slide_count=req.slide_count,
        audience=req.audience,
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
async def get_slide_job_status(job_id: str):
    """Poll progress and status of a slide generation job."""
    slide_job = get_slide_job(job_id)
    if slide_job is None:
        blog_record = get_job(job_id)
        if blog_record is None:
            raise HTTPException(status_code=404, detail="Job not found")
        raise HTTPException(status_code=404, detail="Slide generation not started for this job")

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
    format: str = Query("pdf", regex="^(pdf|pptx|tex)$"),
):
    """
    Download generated slides artifact (pdf, pptx, or tex).
    Returns 409 if generation is not done.
    """
    slide_job = get_slide_job(job_id)
    if slide_job is None:
        raise HTTPException(status_code=404, detail="Slide job not found")
    if slide_job.status == "error":
        raise HTTPException(status_code=500, detail=slide_job.error or "Slide generation failed")
    if slide_job.status != "done":
        raise HTTPException(
            status_code=409,
            detail=f"Slide job not completed yet (status: {slide_job.status}, stage: {slide_job.stage})",
        )

    # Sanitize title for filename
    raw_title = slide_job.title or "slides"
    safe_title = re.sub(r"[^\w\-_]+", "_", raw_title).strip("_") or "slides"

    if format == "pdf":
        if not slide_job.pdf_bytes:
            raise HTTPException(
                status_code=404,
                detail="PDF artifact not available. A LaTeX engine may not be installed on the server.",
            )
        return Response(
            content=slide_job.pdf_bytes,
            media_type="application/pdf",
            headers={"Content-Disposition": f'attachment; filename="{safe_title}.pdf"'},
        )
    elif format == "pptx":
        if not slide_job.pptx_bytes:
            raise HTTPException(status_code=404, detail="PPTX artifact not available.")
        return Response(
            content=slide_job.pptx_bytes,
            media_type="application/vnd.openxmlformats-officedocument.presentationml.presentation",
            headers={"Content-Disposition": f'attachment; filename="{safe_title}.pptx"'},
        )
    elif format == "tex":
        if not slide_job.tex_content:
            raise HTTPException(status_code=404, detail="TeX source artifact not available.")
        return Response(
            content=slide_job.tex_content.encode("utf-8"),
            media_type="text/x-tex; charset=utf-8",
            headers={"Content-Disposition": f'attachment; filename="{safe_title}.tex"'},
        )

