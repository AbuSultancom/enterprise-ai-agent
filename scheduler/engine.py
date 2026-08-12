"""
Scheduler engine - runs AI agent tasks on a schedule.

Supports cron and interval jobs. Jobs persist in data/scheduled_jobs.json.

Environment:
  SCHEDULER_ENABLED=true          -- enable scheduler (default: true)
  SCHEDULER_TIMEZONE=Asia/Riyadh  -- for display only (asyncio uses local time)
  WHATSAPP_BRIDGE_URL             -- URL of the WhatsApp bridge send endpoint
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import uuid
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

ROOT = Path(__file__).parent.parent.resolve()
JOBS_FILE = ROOT / "data" / "scheduled_jobs.json"
ENABLED = os.getenv("SCHEDULER_ENABLED", "true").lower() == "true"


class ScheduledJob:
    """Represents one scheduled task."""

    FIELDS = (
        "job_id",
        "name",
        "prompt",
        "trigger",
        "hour",
        "minute",
        "day_of_week",
        "interval_minutes",
        "notify_whatsapp",
        "notify_telegram",
        "notify_email",
        "enabled",
        "created_at",
        "last_run",
        "last_result",
        "run_count",
    )

    def __init__(
        self,
        *,
        job_id: str | None = None,
        name: str,
        prompt: str,
        trigger: str = "cron",
        hour: int | None = 8,
        minute: int = 0,
        day_of_week: str = "*",
        interval_minutes: int = 60,
        notify_whatsapp: str = "",
        notify_telegram: str = "",
        notify_email: str = "",
        enabled: bool = True,
        created_at: str | None = None,
        last_run: str | None = None,
        last_result: str | None = None,
        run_count: int = 0,
    ):
        self.job_id = job_id or str(uuid.uuid4())[:8]
        self.name = name
        self.prompt = prompt
        self.trigger = trigger
        self.hour = hour
        self.minute = minute
        self.day_of_week = day_of_week
        self.interval_minutes = interval_minutes
        self.notify_whatsapp = notify_whatsapp
        self.notify_telegram = notify_telegram
        self.notify_email = notify_email
        self.enabled = enabled
        self.created_at = created_at or datetime.now().isoformat()
        self.last_run = last_run
        self.last_result = last_result
        self.run_count = run_count

    def to_dict(self) -> dict:
        return {f: getattr(self, f) for f in self.FIELDS}

    @classmethod
    def from_dict(cls, d: dict) -> ScheduledJob:
        valid = {k: v for k, v in d.items() if k in cls.FIELDS}
        return cls(**valid)


class SchedulerEngine:
    """Manages all scheduled jobs using pure asyncio tasks."""

    def __init__(self) -> None:
        self._jobs: dict[str, ScheduledJob] = {}
        self._tasks: dict[str, asyncio.Task] = {}
        self._gateway: Any = None
        self._running = False

    def init(self, gateway: Any) -> None:
        self._gateway = gateway

    # --- Persistence -------------------------------------------------------

    def _save(self) -> None:
        JOBS_FILE.parent.mkdir(parents=True, exist_ok=True)
        with open(JOBS_FILE, "w", encoding="utf-8") as f:
            json.dump([j.to_dict() for j in self._jobs.values()], f, ensure_ascii=False, indent=2)

    def _load(self) -> None:
        if not JOBS_FILE.exists():
            return
        try:
            with open(JOBS_FILE, encoding="utf-8") as f:
                for d in json.load(f):
                    job = ScheduledJob.from_dict(d)
                    self._jobs[job.job_id] = job
            logger.info("Scheduler: loaded %d jobs from disk", len(self._jobs))
        except Exception as exc:
            logger.warning("Scheduler: failed to load jobs file: %s", exc)

    # --- CRUD --------------------------------------------------------------

    def list_jobs(self) -> list[dict]:
        return [j.to_dict() for j in self._jobs.values()]

    def get_job(self, job_id: str) -> ScheduledJob | None:
        return self._jobs.get(job_id)

    def add_job(self, job: ScheduledJob) -> ScheduledJob:
        self._jobs[job.job_id] = job
        self._save()
        if self._running and job.enabled:
            self._spawn_task(job)
        logger.info("Scheduler: added job '%s' [%s]", job.name, job.job_id)
        return job

    def update_job(self, job_id: str, updates: dict) -> ScheduledJob | None:
        job = self._jobs.get(job_id)
        if not job:
            return None
        for k, v in updates.items():
            if k in ScheduledJob.FIELDS and k != "job_id":
                setattr(job, k, v)
        self._save()
        self._cancel_task(job_id)
        if self._running and job.enabled:
            self._spawn_task(job)
        return job

    def delete_job(self, job_id: str) -> bool:
        if job_id not in self._jobs:
            return False
        self._cancel_task(job_id)
        del self._jobs[job_id]
        self._save()
        return True

    def toggle_job(self, job_id: str) -> ScheduledJob | None:
        job = self._jobs.get(job_id)
        if not job:
            return None
        job.enabled = not job.enabled
        self._save()
        if job.enabled:
            self._spawn_task(job)
        else:
            self._cancel_task(job_id)
        return job

    # --- Lifecycle ---------------------------------------------------------

    async def start(self) -> None:
        if not ENABLED:
            logger.info("Scheduler: disabled (SCHEDULER_ENABLED=false)")
            return
        self._load()
        self._running = True
        for job in self._jobs.values():
            if job.enabled:
                self._spawn_task(job)
        logger.info("Scheduler: started with %d active tasks", len(self._tasks))

    async def stop(self) -> None:
        self._running = False
        for task in list(self._tasks.values()):
            task.cancel()
        self._tasks.clear()
        logger.info("Scheduler: stopped")

    # --- Internal ----------------------------------------------------------

    def _spawn_task(self, job: ScheduledJob) -> None:
        self._cancel_task(job.job_id)
        task = asyncio.create_task(self._job_loop(job), name=f"sched_{job.job_id}")
        self._tasks[job.job_id] = task

    def _cancel_task(self, job_id: str) -> None:
        task = self._tasks.pop(job_id, None)
        if task and not task.done():
            task.cancel()

    def _seconds_until_next_cron(self, job: ScheduledJob) -> float:
        now = datetime.now()
        target_h = job.hour if job.hour is not None else 8
        target_m = job.minute
        next_run = now.replace(hour=target_h, minute=target_m, second=0, microsecond=0)
        if next_run <= now:
            next_run += timedelta(days=1)
        return (next_run - now).total_seconds()

    async def _job_loop(self, job: ScheduledJob) -> None:
        logger.info("Scheduler: loop started for job '%s'", job.name)
        try:
            while True:
                if job.trigger == "cron":
                    wait = self._seconds_until_next_cron(job)
                else:
                    wait = float(job.interval_minutes * 60)

                logger.debug("Scheduler: '%s' sleeping %.0fs", job.name, wait)
                await asyncio.sleep(wait)

                current = self._jobs.get(job.job_id)
                if not current or not current.enabled:
                    break
                await self._execute_job(current)

        except asyncio.CancelledError:
            logger.info("Scheduler: loop for '%s' cancelled", job.name)

    async def _execute_job(self, job: ScheduledJob) -> None:
        logger.info("Scheduler: EXECUTING '%s' — %s", job.name, job.prompt[:80])
        job.last_run = datetime.now().isoformat()
        job.run_count += 1
        self._save()

        try:
            if self._gateway is None:
                raise RuntimeError("LLM Gateway not initialized in scheduler")
            from orchestrator.agent import OrchestratorAgent

            agent = OrchestratorAgent(self._gateway)
            result = await agent.run(job.prompt)
            answer = result.get("answer", "No answer.")
        except Exception as exc:
            logger.error("Scheduler: job '%s' agent error: %s", job.name, exc, exc_info=True)
            answer = f"[Scheduler] Job '{job.name}' failed: {exc}"

        job.last_result = answer[:500]
        self._save()
        logger.info("Scheduler: '%s' completed — delivering to channels", job.name)
        await self._deliver(job, answer)

    async def _deliver(self, job: ScheduledJob, message: str) -> None:
        header = f"📅 *{job.name}*\n{datetime.now().strftime('%Y-%m-%d %H:%M')}\n\n"
        full_msg = header + message

        if job.notify_whatsapp:
            bridge_url = os.getenv("WHATSAPP_BRIDGE_URL", "http://localhost:3001")
            try:
                import httpx

                async with httpx.AsyncClient(timeout=30) as client:
                    for number in job.notify_whatsapp.split(","):
                        number = number.strip()
                        if number:
                            await client.post(
                                f"{bridge_url}/send", json={"number": number, "message": full_msg}
                            )
            except Exception as exc:
                logger.warning("Scheduler: WhatsApp delivery failed: %s", exc)

        if job.notify_email:
            try:
                from tools.communication import send_email_notification

                for email in job.notify_email.split(","):
                    email = email.strip()
                    if email:
                        await send_email_notification(email, f"📅 {job.name}", full_msg)
            except Exception as exc:
                logger.warning("Scheduler: Email delivery failed: %s", exc)


# Global singleton
scheduler_engine = SchedulerEngine()
