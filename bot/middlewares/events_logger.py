"""Lightweight update audit middleware."""
from aiogram import BaseMiddleware
from aiogram.types import Message, CallbackQuery


class EventsLoggerMiddleware(BaseMiddleware):
    def __init__(self, repo) -> None:
        self.repo = repo

    async def __call__(self, handler, event, data):
        user = getattr(event, "from_user", None)
        if user:
            try:
                await self.repo.upsert_user(user.id, getattr(user, "username", None), getattr(user, "first_name", "") or "")
                event_type = "callback" if isinstance(event, CallbackQuery) else "message"
                await self.repo.log_event(event_type, user.id, {"update_type": type(event).__name__})
            except Exception:
                pass
        return await handler(event, data)
