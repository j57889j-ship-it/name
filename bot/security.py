"""Shared authorization helpers."""
from bot.config import settings


def is_admin(user_id: int | None) -> bool:
    """Return whether a Telegram user is one of the configured owners/admins."""
    return user_id is not None and user_id in settings.admin_ids
