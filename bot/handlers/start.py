"""Private user entry flow and hidden-command fallback."""
from aiogram import Router, F
from aiogram.filters import CommandStart, Command
from aiogram.types import Message, CallbackQuery
from bot.config import settings
from bot.security import is_admin
from bot.ui import keyboards, texts
from bot.ui.fx import boot_sequence
from bot.handlers.common import admin_callback_guard
from bot.handlers.admin.panel import render_admin_home

router = Router(name="public-start")


@router.message(CommandStart())
async def start_handler(message: Message, repo, subscription_service, state) -> None:
    await state.clear()
    args = (message.text or "").split(maxsplit=1)
    source = args[1][:80] if len(args) > 1 else None
    await repo.upsert_user(message.from_user.id, message.from_user.username, message.from_user.first_name or "", source)
    await repo.log_event("start", message.from_user.id, {"source": source})
    if is_admin(message.from_user.id):
        sent = await message.answer("<code>root@dasturlash:~$ boot</code>")
        effects = await repo.get_setting("effects_enabled", "true") == "true"
        await boot_sequence(sent, effects)
        await sent.edit_text(await render_admin_home(repo), reply_markup=keyboards.admin_home())
        return
    if not await subscription_service.is_member(message.from_user.id):
        await message.answer(texts.SUBSCRIBE, reply_markup=keyboards.subscription(f"https://t.me/{settings.channel_username}"))
        return
    await message.answer(texts.USER_HOME, reply_markup=keyboards.user_home())


@router.message(Command("help"))
async def help_handler(message: Message, subscription_service) -> None:
    if is_admin(message.from_user.id):
        await message.answer(texts.ADMIN_HOME, reply_markup=keyboards.admin_home())
    elif await subscription_service.is_member(message.from_user.id):
        await message.answer(texts.USER_HELP, reply_markup=keyboards.user_home())
    else:
        await message.answer(texts.SUBSCRIBE, reply_markup=keyboards.subscription(f"https://t.me/{settings.channel_username}"))


@router.callback_query(F.data == "sub:check")
async def check_subscription(callback: CallbackQuery, subscription_service, state) -> None:
    await callback.answer()
    if await subscription_service.is_member(callback.from_user.id):
        await state.clear()
        if callback.message:
            await callback.message.edit_text(texts.USER_HOME, reply_markup=keyboards.user_home())
    else:
        if callback.message:
            await callback.message.edit_text(texts.SUBSCRIBE, reply_markup=keyboards.subscription(f"https://t.me/{settings.channel_username}"))


@router.callback_query(F.data == "user:contact")
async def contact_entry(callback: CallbackQuery, state) -> None:
    await callback.answer()
    if callback.message:
        from bot.states import SupportStates
        await state.set_state(SupportStates.waiting_message)
        await callback.message.edit_text(
            "💬 <b>Adminga murojaat</b>\n\nXabaringizni matn, rasm, video, ovoz yoki hujjat ko‘rinishida yuboring.\n/cancel — bekor qilish."
        )


@router.message(Command("cancel"))
async def public_cancel(message: Message, state) -> None:
    await state.clear()
    if is_admin(message.from_user.id):
        await message.answer("🟡 Amal bekor qilindi.", reply_markup=keyboards.admin_home())
    else:
        await message.answer("🟡 Amal bekor qilindi.", reply_markup=keyboards.user_home())

