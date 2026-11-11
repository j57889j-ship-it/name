"""Admin inbox, ticket status management, and media-capable replies."""
from __future__ import annotations
import html
from aiogram import Router, F
from aiogram.types import CallbackQuery, Message
from aiogram.fsm.context import FSMContext
from bot.middlewares.admin_only import AdminFilter
from bot.handlers.common import admin_callback_guard
from bot.states import AdminStates
from bot.ui import keyboards
from bot.ui.theme import terminal_header

router = Router(name="admin-tickets")
router.message.filter(AdminFilter())
router.callback_query.filter(AdminFilter())


@router.callback_query(F.data == "adm:tickets")
async def tickets_menu(callback: CallbackQuery, repo) -> None:
    if not await admin_callback_guard(callback): return
    await callback.answer()
    rows = await repo.fetch("""SELECT t.id,t.status,t.tag,t.is_starred,u.first_name,u.username
        FROM tickets t JOIN users u ON u.id=t.user_id ORDER BY (t.status='new') DESC,t.created_at DESC LIMIT 12""")
    text = f"{terminal_header('support inbox')}\n\n💬 <b>Murojaatlar</b>\n"
    if rows:
        for row in rows:
            name = "@" + row["username"] if row["username"] else row["first_name"]
            state = {"new": "🆕", "in_progress": "⏳", "closed": "✅"}.get(row["status"], "❔")
            text += f"\n{state} <code>#{row['id']}</code> {html.escape(name or 'Foydalanuvchi')} · {html.escape(row['tag'])} {'⭐' if row['is_starred'] else ''}"
    else:
        text += "Hozircha murojaat yo‘q."
    from aiogram.utils.keyboard import InlineKeyboardBuilder
    builder = InlineKeyboardBuilder()
    for row in rows:
        builder.button(text=f"#{row['id']} · {row['status']}", callback_data=f"ticket:view:{row['id']}")
    builder.adjust(2)
    builder.row(keyboards.__button("🏠 Bosh menyu", "adm:home"))
    if callback.message:
        await callback.message.edit_text(text, reply_markup=builder.as_markup())


@router.callback_query(F.data.startswith("ticket:view:"))
async def ticket_view(callback: CallbackQuery, repo) -> None:
    if not await admin_callback_guard(callback): return
    await callback.answer()
    ticket_id = int((callback.data or "ticket:view:0").split(":")[-1])
    ticket = await repo.get_ticket(ticket_id)
    if not ticket:
        if callback.message: await callback.message.edit_text("Murojaat topilmadi.", reply_markup=keyboards.back_home("adm:tickets"))
        return
    history = await repo.fetch("SELECT sender,text,content_type,created_at FROM ticket_messages WHERE ticket_id=$1 ORDER BY created_at DESC LIMIT 8", ticket_id)
    name = "@" + ticket["username"] if ticket["username"] else ticket["first_name"]
    text = f"{terminal_header('ticket detail')}\n\n<b>#{ticket_id}</b> · {html.escape(name or 'Foydalanuvchi')}\n🆔 <code>{ticket['user_id']}</code>\nHolat: <b>{ticket['status']}</b>\nTeg: <b>{html.escape(ticket['tag'])}</b>\n\n<b>So‘nggi xabarlar:</b>\n"
    for item in reversed(history):
        text += f"\n<code>{'ADMIN' if item['sender']=='admin' else 'USER'}</code> {html.escape((item['text'] or '['+item['content_type']+']')[:240])}"
    if callback.message:
        await callback.message.edit_text(text[:3900], reply_markup=keyboards.ticket_actions(ticket_id))


@router.callback_query(F.data.startswith("ticket:reply:"))
async def ticket_reply_start(callback: CallbackQuery, state: FSMContext) -> None:
    if not await admin_callback_guard(callback): return
    await callback.answer()
    ticket_id = int((callback.data or "ticket:reply:0").split(":")[-1])
    await state.clear()
    await state.update_data(reply_ticket_id=ticket_id)
    await state.set_state(AdminStates.waiting_ticket_reply)
    if callback.message:
        await callback.message.answer(f"↩️ <b>#{ticket_id}</b> murojaatiga javob yuboring. Matn yoki media yuborishingiz mumkin. /cancel — bekor qilish.")


@router.message(AdminStates.waiting_ticket_reply)
async def send_ticket_reply(message: Message, state: FSMContext, repo) -> None:
    data = await state.get_data()
    ticket_id = int(data.get("reply_ticket_id", 0))
    ticket = await repo.get_ticket(ticket_id)
    if not ticket:
        await message.answer("Murojaat topilmadi.")
        await state.clear()
        return
    try:
        sent = await message.bot.copy_message(ticket["user_id"], message.chat.id, message.message_id)
    except Exception as exc:
        await message.answer(f"🔴 Javob yuborilmadi: {html.escape(str(exc)[:250])}")
        return
    kind = message.content_type
    file_id = None
    if message.photo: file_id = message.photo[-1].file_id
    elif message.document: file_id = message.document.file_id
    elif message.video: file_id = message.video.file_id
    elif message.voice: file_id = message.voice.file_id
    text = message.text or message.caption
    await repo.add_ticket_message(ticket_id, "admin", message.from_user.id, kind, text, file_id, sent.message_id)
    await repo.audit(message.from_user.id, "ticket_reply", {"ticket_id": ticket_id, "content_type": kind})
    await message.answer(f"🟢 #{ticket_id} murojaatiga javob yuborildi.")
    await state.clear()


@router.callback_query(F.data.startswith("ticket:close:"))
async def ticket_close(callback: CallbackQuery, repo) -> None:
    if not await admin_callback_guard(callback): return
    await callback.answer("Murojaat yopildi.")
    ticket_id = int((callback.data or "ticket:close:0").split(":")[-1])
    await repo.set_ticket(ticket_id, status="closed")
    if callback.message:
        await callback.message.edit_text(f"✅ #{ticket_id} yopildi.", reply_markup=keyboards.back_home("adm:tickets"))


@router.callback_query(F.data.startswith("ticket:progress:"))
async def ticket_progress(callback: CallbackQuery, repo) -> None:
    if not await admin_callback_guard(callback): return
    await callback.answer("Jarayonga olindi.")
    ticket_id = int((callback.data or "ticket:progress:0").split(":")[-1])
    await repo.set_ticket(ticket_id, status="in_progress")
    if callback.message: await callback.message.edit_text(f"⏳ #{ticket_id} jarayonda.", reply_markup=keyboards.back_home("adm:tickets"))


@router.callback_query(F.data.startswith("ticket:star:"))
async def ticket_star(callback: CallbackQuery, repo) -> None:
    if not await admin_callback_guard(callback): return
    ticket_id = int((callback.data or "ticket:star:0").split(":")[-1])
    row = await repo.fetchrow("SELECT is_starred FROM tickets WHERE id=$1", ticket_id)
    if row:
        await repo.set_ticket(ticket_id, is_starred=not row["is_starred"])
    await callback.answer("Muhimlik belgisi o‘zgartirildi.")


@router.callback_query(F.data.startswith("ticket:tag:"))
async def ticket_tag_menu(callback: CallbackQuery) -> None:
    if not await admin_callback_guard(callback): return
    await callback.answer()
    ticket_id = int((callback.data or "ticket:tag:0").split(":")[-1])
    from aiogram.utils.keyboard import InlineKeyboardBuilder
    builder = InlineKeyboardBuilder()
    for tag in ["savol", "taklif", "shikoyat", "hamkorlik", "reklama"]:
        builder.button(text=tag.title(), callback_data=f"ticket:settag:{ticket_id}:{tag}")
    builder.adjust(2)
    if callback.message: await callback.message.edit_text(f"#{ticket_id} uchun tegni tanlang:", reply_markup=builder.as_markup())


@router.callback_query(F.data.startswith("ticket:settag:"))
async def ticket_set_tag(callback: CallbackQuery, repo) -> None:
    if not await admin_callback_guard(callback): return
    await callback.answer("Teg saqlandi.")
    _, _, ticket_raw, tag = (callback.data or "").split(":", 3)
    await repo.set_ticket(int(ticket_raw), tag=tag)
    if callback.message: await callback.message.edit_text(f"🏷 #{ticket_raw} teg: {html.escape(tag)}", reply_markup=keyboards.back_home("adm:tickets"))


@router.callback_query(F.data.startswith("ticket:ban:"))
async def ticket_ban(callback: CallbackQuery, repo) -> None:
    if not await admin_callback_guard(callback): return
    await callback.answer("Foydalanuvchi bloklandi.", show_alert=True)
    ticket_id = int((callback.data or "ticket:ban:0").split(":")[-1])
    ticket = await repo.get_ticket(ticket_id)
    if ticket:
        await repo.execute("UPDATE users SET is_banned=TRUE WHERE id=$1", ticket["user_id"])
        await repo.audit(callback.from_user.id, "user_banned_from_ticket", {"ticket_id": ticket_id, "user_id": ticket["user_id"]})
    if callback.message: await callback.message.edit_text(f"🚫 #{ticket_id} foydalanuvchisi bloklandi.", reply_markup=keyboards.back_home("adm:tickets"))
