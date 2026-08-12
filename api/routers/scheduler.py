"""Scheduler router — CRUD API for scheduled agent jobs."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from api.dependencies import require_role
from scheduler.engine import ScheduledJob, scheduler_engine

router = APIRouter(prefix="/v1/scheduler", tags=["Scheduler"])


# ── Request models ──────────────────────────────────────────────────────────

class JobRequest(BaseModel):
    name: str = Field(..., description="Human-readable job name")
    prompt: str = Field(..., description="Message to send to the AI agent")
    trigger: str = Field("cron", description="'cron' or 'interval'")
    # Cron fields
    hour: int | None = Field(None, ge=0, le=23, description="Hour to run (cron only)")
    minute: int = Field(0, ge=0, le=59, description="Minute to run (cron only)")
    day_of_week: str = Field("*", description="Days: 'mon-fri' / '*' (cron only)")
    # Interval fields
    interval_minutes: int = Field(60, ge=1, description="Interval in minutes")
    # Delivery
    notify_whatsapp: str = Field("", description="Comma-separated WhatsApp numbers")
    notify_telegram: str = Field("", description="Comma-separated Telegram chat IDs")
    notify_email: str = Field("", description="Comma-separated email addresses")
    enabled: bool = True


class JobUpdateRequest(BaseModel):
    name: str | None = None
    prompt: str | None = None
    trigger: str | None = None
    hour: int | None = None
    minute: int | None = None
    day_of_week: str | None = None
    interval_minutes: int | None = None
    notify_whatsapp: str | None = None
    notify_telegram: str | None = None
    notify_email: str | None = None
    enabled: bool | None = None


# ── Endpoints ───────────────────────────────────────────────────────────────

@router.get("", dependencies=[Depends(require_role("admin", "user"))])
async def list_jobs():
    """List all scheduled jobs."""
    return scheduler_engine.list_jobs()


@router.get("/{job_id}", dependencies=[Depends(require_role("admin", "user"))])
async def get_job(job_id: str):
    """Get a single scheduled job."""
    job = scheduler_engine.get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail=f"Job '{job_id}' not found")
    return job.to_dict()


@router.post("", dependencies=[Depends(require_role("admin"))])
async def create_job(req: JobRequest):
    """Create and schedule a new job."""
    if req.trigger == "cron" and req.hour is None:
        raise HTTPException(status_code=422, detail="Cron jobs require 'hour' field")
    if req.trigger == "interval" and req.interval_minutes < 1:
        raise HTTPException(status_code=422, detail="interval_minutes must be >= 1")

    job = ScheduledJob(
        name=req.name,
        prompt=req.prompt,
        trigger=req.trigger,
        hour=req.hour,
        minute=req.minute,
        day_of_week=req.day_of_week,
        interval_minutes=req.interval_minutes,
        notify_whatsapp=req.notify_whatsapp,
        notify_telegram=req.notify_telegram,
        notify_email=req.notify_email,
        enabled=req.enabled,
    )
    scheduler_engine.add_job(job)
    return job.to_dict()


@router.patch("/{job_id}", dependencies=[Depends(require_role("admin"))])
async def update_job(job_id: str, req: JobUpdateRequest):
    """Update an existing scheduled job."""
    updates = {k: v for k, v in req.model_dump(exclude_unset=True).items() if v is not None}
    job = scheduler_engine.update_job(job_id, updates)
    if not job:
        raise HTTPException(status_code=404, detail=f"Job '{job_id}' not found")
    return job.to_dict()


@router.post("/{job_id}/toggle", dependencies=[Depends(require_role("admin"))])
async def toggle_job(job_id: str):
    """Enable or disable a scheduled job."""
    job = scheduler_engine.toggle_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail=f"Job '{job_id}' not found")
    status = "enabled" if job.enabled else "disabled"
    return {"job_id": job_id, "status": status, "enabled": job.enabled}


@router.delete("/{job_id}", dependencies=[Depends(require_role("admin"))])
async def delete_job(job_id: str):
    """Delete a scheduled job permanently."""
    if not scheduler_engine.delete_job(job_id):
        raise HTTPException(status_code=404, detail=f"Job '{job_id}' not found")
    return {"deleted": job_id}
