"""Mandatory-subscription gate for all regular-user private interactions."""
from __future__ import annotations
from aiogram import BaseMiddleware
from aiogram.types import Message, CallbackQuery
from aiogram.exceptions import TelegramAPIError
from loguru import logger
from bot.config import settings
from bot.security import is_admin
from bot.ui import keyboards, texts


class SubscriptionMiddleware(BaseMiddleware):
    def __init__(self, subscription_service) -> None:
        self.subscription_service = subscription_service

    async def __call__(self, handler, event, data):
        user = getattr(event, "from_user", None)
        if not user or is_admin(user.id):
            return await handler(event, data)
        repo = data.get("repo")
        if repo and await repo.is_banned(user.id):
            return None
        if isinstance(event, Message):
            command = (event.text or "").split(maxsplit=1)[0].lower() if event.text else ""
            command = command.split("@", 1)[0]
            if command in {"/start", "/help", "/cancel"}:
                return await handler(event, data)
            if command == "/admin":
                await event.answer(texts.NOT_FOUND)
                return None
        if isinstance(event, CallbackQuery):
            payload = event.data or ""
            if payload.startswith(("adm:", "ai:", "post:", "set:", "ticket:", "schedule:", "broadcast:", "tool:", "analytics:", "users:", "research:", "security:")):
                await event.answer(texts.NOT_FOUND, show_alert=False)
                return None
            if payload == "sub:check":
                return await handler(event, data)
        if not await self.subscription_service.is_member(user.id):
            if isinstance(event, CallbackQuery):
                await event.answer("Avval kanalga obuna bo‘ling.", show_alert=True)
                if event.message:
                    await event.message.answer(
                        texts.SUBSCRIBE,
                        reply_markup=keyboards.subscription(f"https://t.me/{settings.channel_username}"),
                    )
            elif isinstance(event, Message):
                await event.answer(
                    texts.SUBSCRIBE,
                    reply_markup=keyboards.subscription(f"https://t.me/{settings.channel_username}"),
                )
            return None
        return await handler(event, data)
