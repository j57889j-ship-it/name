"""Common helpers shared by handler modules."""
from aiogram.types import CallbackQuery
from bot.security import is_admin
from bot.ui.texts import NOT_FOUND


async def admin_callback_guard(callback: CallbackQuery) -> bool:
    """Re-check admin identity inside each sensitive callback handler."""
    if not is_admin(callback.from_user.id):
        await callback.answer(NOT_FOUND, show_alert=False)
        return False
    return True
