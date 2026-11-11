"""Regular-user support ticket intake for text and media."""
from __future__ import annotations
import html
from aiogram import Router, F
from aiogram.types import Message
from aiogram.fsm.context import FSMContext
from bot.config import settings
from bot.states import SupportStates
from bot.security import is_admin
from bot.ui.keyboards import ticket_actions, user_home

router = Router(name="user-support")


def _message_content(message: Message) -> tuple[str, str | None, str | None]:
    kind = message.content_type
    file_id = None
    if message.photo:
        file_id = message.photo[-1].file_id
    elif message.document:
        file_id = message.document.file_id
    elif message.video:
        file_id = message.video.file_id
    elif message.voice:
        file_id = message.voice.file_id
    elif message.audio:
        file_id = message.audio.file_id
    elif message.video_note:
        file_id = message.video_note.file_id
    return kind, message.text or message.caption, file_id


@router.message(SupportStates.waiting_message)
async def receive_support_message(message: Message, state: FSMContext, repo, runtime) -> None:
    user_id = message.from_user.id
    if await repo.is_banned(user_id):
        return
    kind, text, file_id = _message_content(message)
    if text and len(text) > settings.max_user_message_length:
        await message.answer(f"⚠️ Xabar {settings.max_user_message_length} belgidan oshmasligi kerak.")
        return
    if kind not in {"text", "photo", "video", "document", "voice", "audio", "video_note", "animation", "sticker"}:
        await message.answer("⚠️ Bu xabar turi qo‘llab-quvvatlanmaydi.")
        return
    await repo.upsert_user(user_id, message.from_user.username, message.from_user.first_name or "")
    ticket_id = await repo.open_ticket(user_id)
    is_new_ticket = ticket_id is None
    if ticket_id is None:
        opened_today = await repo.fetchrow(
            "SELECT COUNT(*) AS n FROM tickets WHERE user_id=$1 AND created_at >= ((NOW() AT TIME ZONE 'Asia/Tashkent')::date::timestamp AT TIME ZONE 'Asia/Tashkent')",
            user_id,
        )
        if int(opened_today["n"]) >= settings.max_open_tickets_per_day:
            await message.answer("⛔ Bugun uchun ochiq murojaatlar limiti tugadi.")
            await state.clear()
            return
        ticket_id = await repo.create_ticket(user_id)
    await repo.add_ticket_message(ticket_id, "user", user_id, kind, text, file_id, message.message_id)
    await repo.log_event("ticket_created", user_id, {"ticket_id": ticket_id, "content_type": kind})
    username = html.escape(f"@{message.from_user.username}" if message.from_user.username else (message.from_user.full_name or "Foydalanuvchi"))
    header = (
        f"{'🆕 YANGI MUROJAAT' if is_new_ticket else '💬 MUROJAAT DAVOMI'} <b>#{ticket_id}</b>\n"
        f"👤 {username}\n🆔 <code>{user_id}</code>\n"
        f"📅 {message.date:%Y-%m-%d %H:%M}\n"
        f"🏷 Manba: foydalanuvchi bot\n📌 Holat: Yangi"
    )
    notify_admin = await repo.get_setting("notify_new_ticket", "true") == "true"
    if notify_admin:
        for admin_id in settings.admin_ids:
            try:
                await message.bot.send_message(admin_id, header, reply_markup=ticket_actions(ticket_id))
                await message.bot.copy_message(admin_id, message.chat.id, message.message_id)
            except Exception:
                await repo.log_event("ticket_admin_delivery_failed", user_id, {"ticket_id": ticket_id, "admin_id": admin_id})
    await message.answer(f"🟢 <b>[ SENT ]</b> #{ticket_id} raqamli murojaatingiz qabul qilindi. Admin javobini shu bot orqali olasiz.", reply_markup=user_home())
    await state.clear()
