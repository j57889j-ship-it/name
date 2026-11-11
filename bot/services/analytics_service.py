"""Aggregated analytics for private admin reports."""
from __future__ import annotations


class AnalyticsService:
    def __init__(self, repo) -> None:
        self.repo = repo

    async def dashboard(self) -> dict:
        rows = await self.repo.fetchrow("""SELECT
            (SELECT COUNT(*) FROM users WHERE is_banned=FALSE) AS users,
            (SELECT COUNT(*) FROM users WHERE joined_at::date=CURRENT_DATE) AS new_today,
            (SELECT COUNT(*) FROM tickets WHERE status<>'closed') AS open_tickets,
            (SELECT COUNT(*) FROM scheduled_jobs WHERE active=TRUE) AS scheduled_posts,
            (SELECT COUNT(*) FROM posts WHERE status='published' AND published_at::date=CURRENT_DATE) AS posts_today""")
        return dict(rows)

    async def user_growth(self) -> list[dict]:
        rows = await self.repo.fetch("""SELECT joined_at::date AS day,COUNT(*) AS total
            FROM users WHERE joined_at >= NOW()-INTERVAL '30 days'
            GROUP BY joined_at::date ORDER BY day""")
        return [{"day": str(r["day"]), "total": int(r["total"])} for r in rows]

    async def support_metrics(self) -> dict:
        row = await self.repo.fetchrow("""SELECT COUNT(*) AS total,
            COUNT(*) FILTER (WHERE status='closed') AS closed,
            COUNT(*) FILTER (WHERE status<>'closed') AS opened,
            ROUND(AVG(EXTRACT(EPOCH FROM (first_reply_at-created_at))/60)::numeric,1) AS avg_first_reply_minutes
            FROM tickets WHERE created_at >= NOW()-INTERVAL '30 days'""")
        return dict(row)

    async def active_hours(self) -> list[dict]:
        rows = await self.repo.fetch("""SELECT EXTRACT(HOUR FROM ts AT TIME ZONE $1)::int AS hour,COUNT(*) AS hits
            FROM events WHERE ts >= NOW()-INTERVAL '30 days' GROUP BY 1 ORDER BY 1""", "Asia/Tashkent")
        return [{"hour": int(r["hour"]), "hits": int(r["hits"])} for r in rows]
