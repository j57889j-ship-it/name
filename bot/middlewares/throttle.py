"""Per-user message throttle."""
from aiogram import BaseMiddleware
from aiogram.types import Message
from bot.config import settings
from bot.security import is_admin
from bot.states import SupportStates


class UserThrottleMiddleware(BaseMiddleware):
    def __init__(self, runtime) -> None:
        self.runtime = runtime

    async def __call__(self, handler, event, data):
        if isinstance(event, Message) and event.from_user and not is_admin(event.from_user.id):
            state = data.get("state")
            current_state = await state.get_state() if state else None
            if current_state != SupportStates.waiting_message.state:
                return await handler(event, data)
            allowed, _ = await self.runtime.hit_limit(f"throttle:{event.from_user.id}", 1, settings.anti_spam_seconds)
            if not allowed:
                await event.answer(f"⏳ Iltimos, keyingi xabarni {settings.anti_spam_seconds} soniyadan keyin yuboring.")
                return None
        return await handler(event, data)
