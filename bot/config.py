"""Validated application settings loaded from environment variables."""
from __future__ import annotations

import os
import secrets
import re
from zoneinfo import ZoneInfo
from dataclasses import dataclass
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()


@dataclass(frozen=True, slots=True)
class Settings:
    bot_token: str
    admin_ids: frozenset[int]
    channel_id: int
    channel_username: str
    database_url: str
    redis_url: str
    bot_mode: str
    webhook_base_url: str
    webhook_path: str
    webhook_secret: str
    port: int
    ai_provider: str
    openai_api_key: str
    anthropic_api_key: str
    openai_model: str
    anthropic_model: str
    openai_input_usd_per_mtok: float
    openai_output_usd_per_mtok: float
    anthropic_input_usd_per_mtok: float
    anthropic_output_usd_per_mtok: float
    ai_timeout_seconds: int
    ai_daily_request_limit: int
    timezone: str
    backup_chat_id: int
    subscription_required: bool
    effects_enabled: bool
    auto_reaction_enabled: bool
    auto_reaction_emoji: str
    anti_spam_seconds: int
    max_open_tickets_per_day: int
    max_user_message_length: int
    tavily_api_key: str
    log_level: str
    project_root: Path

    @property
    def webhook_url(self) -> str:
        return f"{self.webhook_base_url.rstrip('/')}{self.webhook_path}"

    @classmethod
    def from_env(cls) -> "Settings":
        def required(name: str) -> str:
            value = os.getenv(name, "").strip()
            if not value:
                raise ValueError(f".env sozlamasi yetishmayapti: {name}")
            return value

        try:
            admin_ids = frozenset(int(x.strip()) for x in required("ADMIN_IDS").split(",") if x.strip())
            if not admin_ids:
                raise ValueError("ADMIN_IDS ichida kamida bitta Telegram ID bo'lishi kerak")
            provider = os.getenv("AI_PROVIDER", "openai").strip().lower()
            if provider not in {"openai", "anthropic"}:
                raise ValueError("AI_PROVIDER faqat openai yoki anthropic bo'lishi mumkin")
            openai_key = os.getenv("OPENAI_API_KEY", "").strip()
            anthropic_key = os.getenv("ANTHROPIC_API_KEY", "").strip()
            if provider == "openai" and not openai_key:
                raise ValueError("AI_PROVIDER=openai bo'lsa OPENAI_API_KEY kerak")
            if provider == "anthropic" and not anthropic_key:
                raise ValueError("AI_PROVIDER=anthropic bo'lsa ANTHROPIC_API_KEY kerak")
            channel_id = int(required("CHANNEL_ID"))
            channel_username = required("CHANNEL_USERNAME").lstrip("@")
            mode = os.getenv("BOT_MODE", "webhook").strip().lower()
            if mode not in {"webhook", "polling"}:
                raise ValueError("BOT_MODE webhook yoki polling bo‘lishi kerak")
            backup_raw = os.getenv("BACKUP_CHAT_ID", "").strip()
            backup_id = int(backup_raw) if backup_raw else min(admin_ids)
            path = os.getenv("WEBHOOK_PATH", "/telegram/webhook").strip()
            if not path.startswith("/"):
                path = "/" + path
            secret = os.getenv("WEBHOOK_SECRET", "").strip() or secrets.token_urlsafe(32)
            if len(secret) < 32 or not re.fullmatch(r"[A-Za-z0-9_-]{32,256}", secret):
                raise ValueError("WEBHOOK_SECRET 32–256 belgi va faqat A-Z, a-z, 0-9, _ yoki - dan iborat bo‘lishi kerak")
            timezone_name = os.getenv("TIMEZONE", "Asia/Tashkent").strip()
            try:
                ZoneInfo(timezone_name)
            except Exception as exc:
                raise ValueError(f"TIMEZONE noto‘g‘ri: {timezone_name}") from exc
            webhook_base = os.getenv("WEBHOOK_BASE_URL", "").strip()
            if mode == "webhook" and not webhook_base:
                webhook_base = os.getenv("RENDER_EXTERNAL_URL", "").strip()
            if mode == "webhook" and not webhook_base:
                raise ValueError("WEBHOOK_BASE_URL yoki Render RENDER_EXTERNAL_URL sozlanishi kerak")
            if mode == "webhook" and not webhook_base.startswith("https://"):
                raise ValueError("Telegram webhook manzili HTTPS bo‘lishi kerak")
            return cls(
                bot_token=required("BOT_TOKEN"), admin_ids=admin_ids, channel_id=channel_id,
                channel_username=channel_username, database_url=required("DATABASE_URL"), redis_url=required("REDIS_URL"),
                bot_mode=mode, webhook_base_url=webhook_base or "http://localhost", webhook_path=path, webhook_secret=secret,
                port=int(os.getenv("PORT", "10000")), ai_provider=provider,
                openai_api_key=openai_key, anthropic_api_key=anthropic_key,
                openai_model=os.getenv("OPENAI_MODEL", "gpt-5.4-mini").strip(),
                anthropic_model=os.getenv("ANTHROPIC_MODEL", "claude-sonnet-5").strip(),
                openai_input_usd_per_mtok=float(os.getenv("OPENAI_INPUT_USD_PER_MTOK", "0.75")),
                openai_output_usd_per_mtok=float(os.getenv("OPENAI_OUTPUT_USD_PER_MTOK", "4.50")),
                anthropic_input_usd_per_mtok=float(os.getenv("ANTHROPIC_INPUT_USD_PER_MTOK", "2.00")),
                anthropic_output_usd_per_mtok=float(os.getenv("ANTHROPIC_OUTPUT_USD_PER_MTOK", "10.00")),
                ai_timeout_seconds=int(os.getenv("AI_TIMEOUT_SECONDS", "45")),
                ai_daily_request_limit=int(os.getenv("AI_DAILY_REQUEST_LIMIT", "100")),
                timezone=timezone_name, backup_chat_id=backup_id,
                subscription_required=os.getenv("SUBSCRIPTION_REQUIRED", "true").lower() == "true",
                effects_enabled=os.getenv("EFFECTS_ENABLED", "true").lower() == "true",
                auto_reaction_enabled=os.getenv("AUTO_REACTION_ENABLED", "true").lower() == "true",
                auto_reaction_emoji=os.getenv("AUTO_REACTION_EMOJI", "🔥").strip(),
                anti_spam_seconds=max(5, int(os.getenv("ANTI_SPAM_SECONDS", "30"))),
                max_open_tickets_per_day=max(1, int(os.getenv("MAX_OPEN_TICKETS_PER_DAY", os.getenv("MAX_SUPPORT_MESSAGES_PER_DAY", "20")))),
                max_user_message_length=max(500, int(os.getenv("MAX_USER_MESSAGE_LENGTH", "4000"))),
                tavily_api_key=os.getenv("TAVILY_API_KEY", "").strip(),
                log_level=os.getenv("LOG_LEVEL", "INFO").upper(), project_root=Path(__file__).resolve().parent.parent,
            )
        except ValueError:
            raise
        except Exception as exc:
            raise ValueError(f"Konfiguratsiya xatosi: {exc}") from exc


settings = Settings.from_env()
