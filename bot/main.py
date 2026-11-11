"""Webhook-first Telegram bot entry point for Render Free."""
from __future__ import annotations

import asyncio
import hmac
import json
import logging
import sys
from datetime import datetime
from zoneinfo import ZoneInfo
from pathlib import Path

from aiohttp import web
from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.fsm.storage.redis import RedisStorage
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import Update, BotCommand, BotCommandScopeDefault, BotCommandScopeChat, ErrorEvent
from aiogram.exceptions import TelegramAPIError
from apscheduler.triggers.cron import CronTrigger
from loguru import logger

from bot.config import settings
from bot.db.database import Database
from bot.db.repo import Repository
from bot.services.runtime import RuntimeStore
from bot.services.subscription import SubscriptionService
from bot.services.ai_service import AIService
from bot.ai.client import ai_client
from bot.services.post_service import PostService
from bot.services.scheduler_service import SchedulerService
from bot.services.analytics_service import AnalyticsService
from bot.services.backup_service import create_backup
from bot.middlewares.subscription import SubscriptionMiddleware
from bot.middlewares.throttle import UserThrottleMiddleware
from bot.middlewares.events_logger import EventsLoggerMiddleware
from bot.handlers import start, support_user, fallback, reactions
from bot.handlers.admin import panel, ai_prompts, posts, scheduler_ui, tickets, analytics, settings as admin_settings, tools, broadcast, users, research, security

BASE_DIR = Path(__file__).resolve().parent.parent


def configure_logging() -> None:
    """Configure console and rotating file logs."""
    log_dir = BASE_DIR / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    logger.remove()
    logger.add(sys.stderr, level=settings.log_level, colorize=True,
               format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level}</level> | {message}")
    logger.add(log_dir / "bot.log", rotation="5 MB", retention="7 days", compression="zip", level=settings.log_level)


async def verify_channel_access(bot: Bot) -> None:
    """Fail early unless the bot can publish in the configured channel."""
    me = await bot.get_me()
    member = await bot.get_chat_member(settings.channel_id, me.id)
    status = getattr(member.status, "value", str(member.status))
    if status == "creator":
        return
    if status != "administrator":
        raise RuntimeError("Bot kanal administratori emas. @dasturlash_ai kanaliga botni Administrator qilib qo‘shing.")
    missing = []
    if not bool(getattr(member, "can_post_messages", False)):
        missing.append("Post Messages")
    if not bool(getattr(member, "can_edit_messages", False)):
        missing.append("Edit Messages")
    if not bool(getattr(member, "can_delete_messages", False)):
        missing.append("Delete Messages")
    if missing:
        raise RuntimeError("Kanal admin huquqlari yetarli emas. Botga quyidagi huquqlarni yoqing: " + ", ".join(missing) + ".")


async def configure_commands(bot: Bot) -> None:
    """Show only public commands to users and admin commands to owners."""
    await bot.set_my_commands(
        [BotCommand(command="start", description="Botni boshlash"), BotCommand(command="help", description="Yordam")],
        scope=BotCommandScopeDefault(),
    )
    for admin_id in settings.admin_ids:
        await bot.set_my_commands(
            [BotCommand(command="start", description="Boshlash"), BotCommand(command="admin", description="Boshqaruv paneli")],
            scope=BotCommandScopeChat(chat_id=admin_id),
        )


async def main() -> None:
    configure_logging()
    logger.info("Starting Dasturlash & AI Control Bot")
    print("\n╔══════════════════════════════════════════════╗\n║    DASTURLASH & AI / PRIVATE CONTROL BOT     ║\n║          WEBHOOK • POSTGRES • REDIS           ║\n╚══════════════════════════════════════════════╝\n")

    database = Database(settings.database_url, BASE_DIR / "bot" / "db" / "schema.sql")
    await database.connect()
    repo = Repository(database.require_pool())
    runtime = RuntimeStore(settings.redis_url)
    redis_ok = await runtime.ping()
    if not redis_ok:
        logger.warning("Redis is unavailable; ephemeral rate-limit/cache fallback is active")

    bot = Bot(settings.bot_token, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
    try:
        await verify_channel_access(bot)
        await configure_commands(bot)
    except Exception as exc:
        logger.exception("Channel access verification failed")
        for admin_id in settings.admin_ids:
            try:
                await bot.send_message(admin_id, f"🔴 <b>Bot ishga tushmadi</b>\n{__import__('html').escape(str(exc))}")
            except Exception:
                pass
        await bot.session.close()
        await runtime.close()
        await database.close()
        raise

    storage = RedisStorage.from_url(settings.redis_url) if redis_ok else MemoryStorage()
    dp = Dispatcher(storage=storage)
    post_service = PostService(bot, repo)
    scheduler_service = SchedulerService(repo, post_service)
    ai_service = AIService(repo)
    analytics_service = AnalyticsService(repo)
    subscription_service = SubscriptionService(bot, runtime, repo)

    # Pass dependencies to every handler through aiogram workflow data.
    dp["repo"] = repo
    dp["runtime"] = runtime
    dp["subscription_service"] = subscription_service
    dp["ai_service"] = ai_service
    dp["post_service"] = post_service
    dp["scheduler_service"] = scheduler_service
    dp["analytics_service"] = analytics_service

    dp.message.outer_middleware(EventsLoggerMiddleware(repo))
    dp.callback_query.outer_middleware(EventsLoggerMiddleware(repo))
    dp.message.outer_middleware(SubscriptionMiddleware(subscription_service))
    dp.callback_query.outer_middleware(SubscriptionMiddleware(subscription_service))
    dp.message.outer_middleware(UserThrottleMiddleware(runtime))

    # Public and admin routers are deliberately separate. Admin routers have their own AdminFilter.
    for current_router in [
        start.router, support_user.router,
        panel.router, ai_prompts.router, posts.router, scheduler_ui.router,
        tickets.router, analytics.router, admin_settings.router, tools.router,
        broadcast.router, users.router, research.router, security.router,
        reactions.router, fallback.router,
    ]:
        dp.include_router(current_router)

    @dp.errors()
    async def global_error_handler(event: ErrorEvent):
        exception = event.exception
        logger.opt(exception=(type(exception), exception, exception.__traceback__)).error("Unhandled update error")
        for admin_id in settings.admin_ids:
            try:
                await bot.send_message(admin_id, "<code>root@dasturlash:~$ system_error</code>\n🔴 Kutilmagan xatolik yuz berdi. Loglar tekshirilsin.")
            except Exception:
                pass
        return True

    await scheduler_service.start()

    async def daily_backup_job() -> None:
        try:
            document = await create_backup(repo)
            await bot.send_document(settings.backup_chat_id, document, caption="💾 <b>Kunlik avtomatik backup</b>")
            await repo.log_event("daily_backup_completed", None, {})
        except Exception as exc:
            logger.exception("Daily backup failed")
            await repo.log_event("daily_backup_failed", None, {"error": str(exc)[:300]})
            try: await bot.send_message(settings.backup_chat_id, "🔴 Kunlik backup bajarilmadi. Tools → Backup bo‘limini tekshiring.")
            except Exception: pass

    async def weekly_report_job() -> None:
        try:
            stats = await analytics_service.dashboard()
            support_stats = await analytics_service.support_metrics()
            report = (
                "📊 <b>HAFTALIK DASTURLASH & AI HISOBOTI</b>\n\n"
                f"Foydalanuvchilar: <b>{stats['users']}</b>\nBugun yangi: <b>{stats['new_today']}</b>\n"
                f"Ochiq murojaatlar: <b>{stats['open_tickets']}</b>\nRejalashtirilgan postlar: <b>{stats['scheduled_posts']}</b>\n"
                f"30 kunlik ticketlar: <b>{support_stats['total']}</b>"
            )
            await bot.send_message(settings.backup_chat_id, report)
        except Exception:
            logger.exception("Weekly report failed")

    scheduler_service.weekly_report_job = weekly_report_job
    scheduler_service.scheduler.add_job(daily_backup_job, CronTrigger(hour=3, minute=0, timezone=ZoneInfo(settings.timezone)), id="daily-backup", replace_existing=True)
    if await repo.get_setting("weekly_report_enabled", "false") == "true":
        scheduler_service.scheduler.add_job(weekly_report_job, CronTrigger(day_of_week="sun", hour=20, minute=0, timezone=ZoneInfo(settings.timezone)), id="weekly-report", replace_existing=True)

    app = web.Application(client_max_size=2 * 1024 * 1024)

    async def health(request: web.Request) -> web.Response:
        try:
            await repo.fetchrow("SELECT 1")
            redis_available = await runtime.ping()
            status = "ok" if redis_available else "degraded"
            code = 200 if redis_available else 503
            return web.json_response(
                {"status": status, "service": "dasturlash-ai-control-bot", "postgres": "ok", "redis": "ok" if redis_available else "unavailable"},
                status=code,
            )
        except Exception:
            return web.json_response({"status": "degraded", "service": "dasturlash-ai-control-bot", "postgres": "unavailable"}, status=503)

    async def telegram_webhook(request: web.Request) -> web.Response:
        supplied = request.headers.get("X-Telegram-Bot-Api-Secret-Token", "")
        if not hmac.compare_digest(supplied, settings.webhook_secret):
            return web.Response(status=403, text="forbidden")
        try:
            payload = await request.json()
            update = Update.model_validate(payload, context={"bot": bot})
            await dp.feed_update(bot, update)
            return web.Response(text="OK")
        except Exception as exc:
            logger.exception("Webhook update failed")
            return web.Response(status=500, text="update failed")

    app.router.add_get("/", health)
    app.router.add_get("/health", health)
    app.router.add_post(settings.webhook_path, telegram_webhook)

    allowed_updates = ["message", "callback_query", "chat_member", "my_chat_member", "message_reaction_count"]
    if settings.bot_mode == "webhook":
        await bot.set_webhook(
            url=settings.webhook_url, secret_token=settings.webhook_secret,
            allowed_updates=allowed_updates, drop_pending_updates=False,
        )
        logger.success(f"Webhook set: {settings.webhook_url}")
    else:
        await bot.delete_webhook(drop_pending_updates=False)
        logger.warning("Polling mode is active (local development only)")

    runner = web.AppRunner(app, access_log=None)
    await runner.setup()
    site = web.TCPSite(runner, host="0.0.0.0", port=settings.port)
    await site.start()
    logger.success(f"HTTP server started on port {settings.port}")

    try:
        if settings.bot_mode == "polling":
            await dp.start_polling(bot, allowed_updates=allowed_updates, close_bot_session=False)
        else:
            await asyncio.Event().wait()
    finally:
        logger.info("Graceful shutdown started")
        await runner.cleanup()
        await scheduler_service.close()
        if settings.bot_mode == "webhook":
            await bot.delete_webhook(drop_pending_updates=False)
        await storage.close()
        await ai_client.close()
        await runtime.close()
        await database.close()
        await bot.session.close()
        logger.info("Shutdown complete")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass
    except Exception:
        logger.exception("Fatal startup error")
        raise
