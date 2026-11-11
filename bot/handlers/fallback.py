"""Last-resort hidden-command and stale-callback responses."""
from aiogram import Router
from aiogram.filters import StateFilter
from aiogram.types import Message, CallbackQuery
from bot.ui.texts import NOT_FOUND

router = Router(name="fallback")


@router.message(StateFilter(None))
async def unknown_message(message: Message) -> None:
    if message.text and message.text.startswith("/"):
        await message.answer(NOT_FOUND)
    elif message.from_user:
        await message.answer(NOT_FOUND)


@router.callback_query()
async def unknown_callback(callback: CallbackQuery) -> None:
    await callback.answer(NOT_FOUND, show_alert=False)
