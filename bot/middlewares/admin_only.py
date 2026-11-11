"""Admin-only filter and callback/message boundary protection."""
from aiogram.filters import BaseFilter
from aiogram.types import TelegramObject
from bot.security import is_admin


class AdminFilter(BaseFilter):
    async def __call__(self, event: TelegramObject) -> bool:
        user = getattr(event, "from_user", None)
        return bool(user and is_admin(user.id))
