"""Admin user lookup, profile, and ban/unban management."""
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

router = Router(name="admin-users")
router.callback_query.filter(AdminFilter())
router.message.filter(AdminFilter())


@router.callback_query(F.data == "adm:users")
async def users_menu(callback: CallbackQuery, state: FSMContext, repo) -> None:
    if not await admin_callback_guard(callback): return
    await callback.answer()
    await state.set_state(AdminStates.waiting_user_search)
    stats = await repo.fetchrow("SELECT COUNT(*) AS total,COUNT(*) FILTER (WHERE is_banned) AS banned FROM users")
    if callback.message:
        await callback.message.edit_text(
            f"{terminal_header('user management')}\n\n👥 Jami: <b>{stats['total']}</b>\n🚫 Bloklangan: <b>{stats['banned']}</b>\n\nID yoki username yuboring:",
            reply_markup=keyboards.back_home(),
        )


@router.message(AdminStates.waiting_user_search)
async def user_search(message: Message, state: FSMContext, repo) -> None:
    query = (message.text or "").strip().lstrip("@")
    if len(query) < 2 or len(query) > 100:
        await message.answer("Qidiruv uchun kamida 2 ta belgi yuboring.")
        return
    if query.isdigit():
        row = await repo.fetchrow("SELECT * FROM users WHERE id=$1", int(query))
    else:
        row = await repo.fetchrow("SELECT * FROM users WHERE username ILIKE $1 ORDER BY joined_at DESC LIMIT 1", query)
    if not row:
        await message.answer("🔎 Foydalanuvchi topilmadi. Boshqa ID yoki username kiriting.")
        return
    from aiogram.utils.keyboard import InlineKeyboardBuilder
    builder = InlineKeyboardBuilder()
    builder.button(text="🚫 Ban / Unban", callback_data=f"users:toggleban:{row['id']}")
    builder.adjust(1)
    builder.row(keyboards.__button("⬅️ Qidiruvni davom ettirish", "adm:users"), keyboards.__button("🏠 Menyu", "adm:home"))
    name = "@" + row["username"] if row["username"] else (row["first_name"] or "Noma’lum")
    text = (f"{terminal_header('user profile')}\n\n👤 <b>{html.escape(name)}</b>\n"
            f"ID: <code>{row['id']}</code>\nManba: <code>{html.escape(row['source'] or 'noma’lum')}</code>\n"
            f"Qo‘shilgan: {row['joined_at']:%Y-%m-%d}\nOxirgi faollik: {row['last_seen']:%Y-%m-%d %H:%M}\n"
            f"Holat: {'🚫 BAN' if row['is_banned'] else '🟢 ACTIVE'}\nIzoh: {html.escape(row['note'] or 'yo‘q')}")
    await message.answer(text, reply_markup=builder.as_markup())
    await state.set_state(None)


@router.callback_query(F.data.startswith("users:toggleban:"))
async def toggle_ban(callback: CallbackQuery, repo) -> None:
    if not await admin_callback_guard(callback): return
    user_id = int((callback.data or "users:toggleban:0").split(":")[-1])
    row = await repo.fetchrow("SELECT is_banned FROM users WHERE id=$1", user_id)
    if not row:
        await callback.answer("Foydalanuvchi topilmadi.", show_alert=True); return
    new_value = not row["is_banned"]
    await repo.execute("UPDATE users SET is_banned=$1 WHERE id=$2", new_value, user_id)
    await repo.audit(callback.from_user.id, "user_ban_toggled", {"user_id": user_id, "is_banned": new_value})
    await callback.answer("Foydalanuvchi bloklandi." if new_value else "Blokdan chiqarildi.", show_alert=True)
    if callback.message: await callback.message.edit_reply_markup(reply_markup=keyboards.back_home("adm:users"))
