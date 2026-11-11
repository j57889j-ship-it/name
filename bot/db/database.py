"""PostgreSQL connection pool and schema initialization."""
from __future__ import annotations

from pathlib import Path
from urllib.parse import urlparse, parse_qsl, urlencode, urlunparse
import asyncpg
from bot.config import settings


class Database:
    def __init__(self, dsn: str, schema_path: Path) -> None:
        self.dsn = dsn
        self.schema_path = schema_path
        self.pool: asyncpg.Pool | None = None

    async def connect(self) -> None:
        parsed = urlparse(self.dsn)
        query = dict(parse_qsl(parsed.query))
        ssl_required = query.pop("sslmode", "") in {"require", "verify-ca", "verify-full"}
        clean_dsn = urlunparse(parsed._replace(query=urlencode(query)))
        self.pool = await asyncpg.create_pool(
            dsn=clean_dsn, min_size=1, max_size=5, command_timeout=30, statement_cache_size=0,
            ssl="require" if ssl_required else None,
        )
        schema = self.schema_path.read_text(encoding="utf-8")
        async with self.pool.acquire() as conn:
            await conn.execute(schema)
            await conn.executemany(
                "INSERT INTO settings(key,value) VALUES($1,$2) ON CONFLICT(key) DO NOTHING",
                [
                    ("subscription_required", str(settings.subscription_required).lower()),
                    ("effects_enabled", str(settings.effects_enabled).lower()),
                    ("auto_reaction_enabled", str(settings.auto_reaction_enabled).lower()),
                    ("auto_reaction_emoji", settings.auto_reaction_emoji),
                    ("notify_new_ticket", "true"), ("weekly_report_enabled", "false"),
                    ("weekly_report_time", "20:00"), ("default_post_style", "terminal"),
                    ("default_post_font", "bold"), ("ai_daily_limit", str(settings.ai_daily_request_limit)),
                    ("ai_provider", settings.ai_provider), ("anti_spam_seconds", str(settings.anti_spam_seconds)),
                    ("publishing_paused", "false"), ("broadcast_paused", "false"),
                ],
            )

    async def close(self) -> None:
        if self.pool:
            await self.pool.close()
            self.pool = None

    def require_pool(self) -> asyncpg.Pool:
        if not self.pool:
            raise RuntimeError("Database hali ulanmagan")
        return self.pool
