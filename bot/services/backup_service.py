"""Logical JSON backup of PostgreSQL data, transferred directly to Telegram."""
from __future__ import annotations
import json
from io import BytesIO
from datetime import date, datetime
from decimal import Decimal
from aiogram.types import BufferedInputFile

TABLES = ["users", "tickets", "ticket_messages", "posts", "prompts", "events", "settings", "ai_usage", "scheduled_jobs", "broadcasts", "audit_log", "referral_links", "post_reaction_snapshots", "drafts", "workflows"]


def _json_default(value):
    if isinstance(value, (datetime, date)): return value.isoformat()
    if isinstance(value, Decimal): return float(value)
    raise TypeError(f"Unsupported backup value: {type(value).__name__}")


async def create_backup(repo) -> BufferedInputFile:
    snapshot = {"format": "dasturlash-ai-backup-v1", "tables": {}}
    for table in TABLES:
        # Table names are a static allowlist above, not user input.
        rows = await repo.fetch(f"SELECT * FROM {table}")
        snapshot["tables"][table] = [dict(row) for row in rows]
    payload = json.dumps(snapshot, ensure_ascii=False, default=_json_default, indent=2).encode("utf-8")
    return BufferedInputFile(payload, filename="dasturlash_ai_backup.json")
