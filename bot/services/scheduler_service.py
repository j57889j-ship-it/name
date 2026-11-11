"""Persisted scheduling backed by APScheduler."""
from __future__ import annotations
from datetime import datetime, timezone
from zoneinfo import ZoneInfo
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.date import DateTrigger
from apscheduler.triggers.cron import CronTrigger
from bot.config import settings


class SchedulerService:
    def __init__(self, repo, post_service) -> None:
        self.repo = repo
        self.post_service = post_service
        self.scheduler = AsyncIOScheduler(timezone=ZoneInfo(settings.timezone))

    async def start(self) -> None:
        self.scheduler.start()
        await self.restore()

    async def restore(self) -> None:
        rows = await self.repo.fetch(
            "SELECT j.*,p.title FROM scheduled_jobs j JOIN posts p ON p.id=j.post_id WHERE j.active=TRUE AND p.status IN ('scheduled','published')"
        )
        for row in rows:
            self._add_job(int(row["id"]), int(row["post_id"]), row["run_at"], row["recurrence"])

    def _add_job(self, job_id: int, post_id: int, run_at: datetime, recurrence: str) -> None:
        ident = f"scheduled-post-{job_id}"
        if recurrence == "daily":
            local = run_at.astimezone(ZoneInfo(settings.timezone))
            trigger = CronTrigger(hour=local.hour, minute=local.minute, start_date=local, timezone=ZoneInfo(settings.timezone))
        elif recurrence.startswith("weekly:"):
            local = run_at.astimezone(ZoneInfo(settings.timezone))
            day = recurrence.split(":", 1)[1]
            trigger = CronTrigger(day_of_week=day, hour=local.hour, minute=local.minute, start_date=local, timezone=ZoneInfo(settings.timezone))
        else:
            now = datetime.now(timezone.utc)
            trigger = DateTrigger(run_date=max(run_at, now), timezone=timezone.utc)
        self.scheduler.add_job(
            self._run_post, trigger=trigger, args=[job_id, post_id, recurrence],
            id=ident, replace_existing=True, max_instances=1, coalesce=True,
        )

    async def schedule_post(self, post_id: int, run_at: datetime, recurrence: str = "once") -> int:
        if recurrence not in {"once", "daily", "weekly:mon", "weekly:tue", "weekly:wed", "weekly:thu", "weekly:fri", "weekly:sat", "weekly:sun"}:
            raise ValueError("Takrorlanish turi noto‘g‘ri")
        job = await self.repo.fetchrow(
            "INSERT INTO scheduled_jobs(post_id,run_at,recurrence) VALUES($1,$2,$3) RETURNING id",
            post_id, run_at, recurrence,
        )
        await self.repo.execute("UPDATE posts SET status='scheduled',scheduled_at=$1,recurrence=$2 WHERE id=$3", run_at, recurrence, post_id)
        self._add_job(int(job["id"]), post_id, run_at, recurrence)
        return int(job["id"])

    async def _run_post(self, job_id: int, post_id: int, recurrence: str) -> None:
        try:
            message_id = await self.post_service.publish(post_id)
            if recurrence == "once":
                await self.repo.execute("UPDATE scheduled_jobs SET active=FALSE WHERE id=$1", job_id)
            await self.repo.log_event("scheduled_post_published", None, {"post_id": post_id, "message_id": message_id, "recurrence": recurrence})
            for admin_id in settings.admin_ids:
                try:
                    await self.post_service.bot.send_message(admin_id, f"🟢 <b>Rejalashtirilgan post nashr qilindi</b>\n<code>POST #{post_id} · MESSAGE #{message_id}</code>")
                except Exception:
                    pass
        except Exception as exc:
            next_status = "scheduled" if recurrence != "once" else "failed"
            await self.repo.execute("UPDATE posts SET status=$1 WHERE id=$2", next_status, post_id)
            await self.repo.log_event("scheduled_post_failed", None, {"post_id": post_id, "error": str(exc)[:300]})
            for admin_id in settings.admin_ids:
                try:
                    await self.post_service.bot.send_message(admin_id, f"🔴 <b>Rejalashtirilgan post yuborilmadi</b>\n<code>POST #{post_id}</code>\n{str(exc)[:250]}")
                except Exception:
                    pass

    async def close(self) -> None:
        if self.scheduler.running:
            self.scheduler.shutdown(wait=False)
