"""Thin asynchronous repository for application data."""
from __future__ import annotations

import json
from typing import Any
from asyncpg import Pool, Record


class Repository:
    def __init__(self, pool: Pool) -> None:
        self.pool = pool

    async def execute(self, query: str, *args: Any) -> str:
        async with self.pool.acquire() as conn:
            return await conn.execute(query, *args)

    async def fetch(self, query: str, *args: Any) -> list[Record]:
        async with self.pool.acquire() as conn:
            return await conn.fetch(query, *args)

    async def fetchrow(self, query: str, *args: Any) -> Record | None:
        async with self.pool.acquire() as conn:
            return await conn.fetchrow(query, *args)

    async def upsert_user(self, user_id: int, username: str | None, first_name: str, source: str | None = None) -> None:
        await self.execute(
            """INSERT INTO users(id,username,first_name,source) VALUES($1,$2,$3,$4)
               ON CONFLICT(id) DO UPDATE SET username=EXCLUDED.username,
               first_name=EXCLUDED.first_name,last_seen=NOW(),source=CASE WHEN EXCLUDED.source IS NOT NULL AND EXCLUDED.source <> 'channel_join' THEN EXCLUDED.source ELSE users.source END""",
            user_id, username, first_name[:128], source,
        )

    async def is_banned(self, user_id: int) -> bool:
        row = await self.fetchrow("SELECT is_banned FROM users WHERE id=$1", user_id)
        return bool(row and row["is_banned"])

    async def create_ticket(self, user_id: int) -> int:
        row = await self.fetchrow(
            "INSERT INTO tickets(user_id,status) VALUES($1,'new') RETURNING id", user_id
        )
        return int(row["id"])

    async def open_ticket(self, user_id: int) -> int | None:
        row = await self.fetchrow(
            "SELECT id FROM tickets WHERE user_id=$1 AND status<>'closed' ORDER BY id DESC LIMIT 1", user_id
        )
        return int(row["id"]) if row else None

    async def add_ticket_message(self, ticket_id: int, sender: str, sender_id: int,
                                 content_type: str, text: str | None, file_id: str | None,
                                 telegram_message_id: int | None) -> None:
        await self.execute(
            """INSERT INTO ticket_messages(ticket_id,sender,sender_id,content_type,text,file_id,telegram_message_id)
               VALUES($1,$2,$3,$4,$5,$6,$7)""",
            ticket_id, sender, sender_id, content_type, text, file_id, telegram_message_id,
        )
        if sender == "admin":
            await self.execute(
                "UPDATE tickets SET first_reply_at=COALESCE(first_reply_at,NOW()),status=CASE WHEN status='new' THEN 'in_progress' ELSE status END WHERE id=$1",
                ticket_id,
            )

    async def get_ticket(self, ticket_id: int) -> Record | None:
        return await self.fetchrow(
            """SELECT t.*,u.username,u.first_name FROM tickets t JOIN users u ON u.id=t.user_id WHERE t.id=$1""",
            ticket_id,
        )

    async def set_ticket(self, ticket_id: int, **fields: Any) -> None:
        allowed = {"status", "tag", "is_starred"}
        assignments, values = [], []
        for key, value in fields.items():
            if key not in allowed:
                raise ValueError("Ticket maydoni ruxsat etilmagan")
            values.append(value)
            assignments.append(f"{key}=${len(values)}")
        if not assignments:
            return
        if fields.get("status") == "closed":
            assignments.append("closed_at=NOW()")
        values.append(ticket_id)
        await self.execute(f"UPDATE tickets SET {', '.join(assignments)} WHERE id=${len(values)}", *values)

    async def get_setting(self, key: str, default: str = "") -> str:
        row = await self.fetchrow("SELECT value FROM settings WHERE key=$1", key)
        return str(row["value"]) if row else default

    async def set_setting(self, key: str, value: str) -> None:
        await self.execute(
            "INSERT INTO settings(key,value) VALUES($1,$2) ON CONFLICT(key) DO UPDATE SET value=EXCLUDED.value,updated_at=NOW()",
            key, value,
        )

    async def log_event(self, event_type: str, user_id: int | None = None, payload: dict[str, Any] | None = None) -> None:
        await self.execute("INSERT INTO events(user_id,type,payload) VALUES($1,$2,$3::jsonb)",
                           user_id, event_type, json.dumps(payload or {}, ensure_ascii=False))

    async def audit(self, admin_id: int, action: str, details: dict[str, Any] | None = None) -> None:
        await self.execute("INSERT INTO audit_log(admin_id,action,details) VALUES($1,$2,$3::jsonb)",
                           admin_id, action, json.dumps(details or {}, ensure_ascii=False))

    async def save_prompt(self, title: str, category: str, body: str, admin_id: int) -> int:
        row = await self.fetchrow(
            "INSERT INTO prompts(title,category,body,created_by) VALUES($1,$2,$3,$4) RETURNING id",
            title[:160], category, body, admin_id,
        )
        return int(row["id"])

    async def list_prompts(self, limit: int = 10, offset: int = 0) -> list[Record]:
        return await self.fetch("SELECT * FROM prompts ORDER BY is_favorite DESC,created_at DESC LIMIT $1 OFFSET $2", limit, offset)

    async def get_prompt(self, prompt_id: int) -> Record | None:
        return await self.fetchrow("SELECT * FROM prompts WHERE id=$1", prompt_id)

    async def search_prompts(self, keyword: str, limit: int = 10) -> list[Record]:
        return await self.fetch(
            "SELECT * FROM prompts WHERE title ILIKE $1 OR body ILIKE $1 OR category ILIKE $1 ORDER BY is_favorite DESC,created_at DESC LIMIT $2",
            f"%{keyword[:100]}%", limit,
        )

    async def save_post(self, title: str, body_html: str, admin_id: int, style: str = "terminal", font: str = "bold", media_type: str | None = None, media_file_id: str | None = None) -> int:
        row = await self.fetchrow(
            "INSERT INTO posts(title,body_html,created_by,style,font,media_type,media_file_id) VALUES($1,$2,$3,$4,$5,$6,$7) RETURNING id",
            title[:180], body_html, admin_id, style, font, media_type, media_file_id,
        )
        return int(row["id"])

    async def get_post(self, post_id: int) -> Record | None:
        return await self.fetchrow("SELECT * FROM posts WHERE id=$1", post_id)

    async def save_ai_usage(self, admin_id: int, provider: str, model: str, purpose: str,
                            input_tokens: int, output_tokens: int, cost: float = 0) -> None:
        await self.execute(
            "INSERT INTO ai_usage(admin_id,provider,model,purpose,input_tokens,output_tokens,estimated_cost_usd) VALUES($1,$2,$3,$4,$5,$6,$7)",
            admin_id, provider, model, purpose, input_tokens, output_tokens, cost,
        )

    async def ai_usage_today(self) -> dict[str, Any]:
        row = await self.fetchrow(
            "SELECT COUNT(*) AS requests,COALESCE(SUM(input_tokens),0) AS input_tokens,COALESCE(SUM(output_tokens),0) AS output_tokens,COALESCE(SUM(estimated_cost_usd),0) AS cost FROM ai_usage WHERE created_at >= date_trunc('day',NOW())"
        )
        return dict(row) if row else {"requests": 0, "input_tokens": 0, "output_tokens": 0, "cost": 0}
