"""Cached Telegram channel-membership checks."""
from __future__ import annotations
from aiogram import Bot
from aiogram.enums import ChatMemberStatus
from aiogram.exceptions import TelegramBadRequest, TelegramForbiddenError
from bot.config import settings
from bot.services.runtime import RuntimeStore


class SubscriptionService:
    def __init__(self, bot: Bot, runtime: RuntimeStore, repo=None) -> None:
        self.bot = bot
        self.runtime = runtime
        self.repo = repo

    async def is_member(self, user_id: int) -> bool:
        if user_id in settings.admin_ids:
            return True
        required = settings.subscription_required
        if self.repo:
            required = await self.repo.get_setting("subscription_required", str(settings.subscription_required).lower()) == "true"
        if not required:
            return True
        key = f"sub:{settings.channel_id}:{user_id}"
        cached = await self.runtime.get(key)
        if cached is not None:
            return cached == "1"
        try:
            member = await self.bot.get_chat_member(settings.channel_id, user_id)
            allowed = member.status in {ChatMemberStatus.MEMBER, ChatMemberStatus.ADMINISTRATOR, ChatMemberStatus.CREATOR}
            if member.status == ChatMemberStatus.RESTRICTED:
                allowed = bool(getattr(member, "is_member", False))
        except (TelegramBadRequest, TelegramForbiddenError):
            allowed = False
        await self.runtime.set(key, "1" if allowed else "0", ttl=60)
        return allowed
