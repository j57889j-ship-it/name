"""Admin broadcast composer with user segments and cancellation."""
from __future__ import annotations
import asyncio
import html
import logging
from aiogram import Router, F
from aiogram.types import CallbackQuery, Message
from aiogram.fsm.context import FSMContext
from aiogram.exceptions import TelegramForbiddenError, TelegramRetryAfter, TelegramAPIError
from bot.middlewares.admin_only import AdminFilter
from bot.handlers.common import admin_callback_guard
from bot.states import AdminStates
from bot.ui import keyboards
from bot.ui.theme import terminal_header
from bot.services.post_service import clean_telegram_html

router = Router(name="admin-broadcast")
router.message.filter(AdminFilter())
router.callback_query.filter(AdminFilter())


@router.callback_query(F.data == "adm:broadcast")
async def broadcast_start(callback: CallbackQuery, state: FSMContext) -> None:
    if not await admin_callback_guard(callback): return
    await callback.answer()
    await state.clear()
    await state.set_state(AdminStates.waiting_broadcast_text)
    if callback.message:
        await callback.message.edit_text(f"{terminal_header('broadcast composer')}\n\n📣 Yuboriladigan xabar matnini yuboring. Ruxsat etilgan Telegram HTML formatidan foydalanishingiz mumkin.", reply_markup=keyboards.back_home())


@router.message(AdminStates.waiting_broadcast_text)
async def broadcast_text_input(message: Message, state: FSMContext) -> None:
    body = clean_telegram_html(message.text or message.caption or "")
    has_media = bool(message.photo or message.video or message.document or message.animation or message.audio or message.voice)
    if (not body and not has_media) or len(body) > 4000:
        await message.answer("⚠️ Xabar 1–4000 belgi bo‘lishi kerak.")
        return
    await state.update_data(
        broadcast_body=body,
        broadcast_source_chat_id=message.chat.id if has_media else None,
        broadcast_source_message_id=message.message_id if has_media else None,
    )
    from aiogram.utils.keyboard import InlineKeyboardBuilder
    builder = InlineKeyboardBuilder()
    builder.button(text="👥 Barcha foydalanuvchilar", callback_data="broadcast:segment:all")
    builder.button(text="🟢 So‘nggi 7 kunda faol", callback_data="broadcast:segment:active")
    builder.button(text="🆕 So‘nggi 7 kunda yangi", callback_data="broadcast:segment:new")
    builder.button(text="🌙 30 kun faol bo‘lmagan", callback_data="broadcast:segment:inactive")
    builder.adjust(1)
    await state.set_state(None)
    media_note = "🖼 Media biriktirilgan (yuqoridagi xabar).\n" if has_media else ""
    await message.answer(f"{terminal_header('audience selector')}\n\n{media_note}Auditoriyani tanlang:\n\n<b>Preview:</b>\n{body or 'Media xabar'}", reply_markup=builder.as_markup())


@router.callback_query(F.data.startswith("broadcast:segment:"))
async def choose_segment(callback: CallbackQuery, state: FSMContext) -> None:
    if not await admin_callback_guard(callback): return
    await callback.answer()
    segment = (callback.data or "broadcast:segment:all").split(":")[-1]
    if segment not in {"all", "active", "new", "inactive"}: return
    await state.update_data(broadcast_segment=segment)
    from aiogram.utils.keyboard import InlineKeyboardBuilder
    builder = InlineKeyboardBuilder()
    builder.button(text="✅ Tasdiqlash va yuborish", callback_data="broadcast:confirm")
    builder.button(text="✏️ Matnni qayta yozish", callback_data="adm:broadcast")
    builder.button(text="🏠 Menyu", callback_data="adm:home")
    builder.adjust(1)
    if callback.message:
        data = await state.get_data()
        media_note = "🖼 Biriktirilgan media ham yuboriladi.\n" if data.get("broadcast_source_message_id") else ""
        await callback.message.edit_text(f"{terminal_header('broadcast confirmation')}\n\nSegment: <b>{segment}</b>\n{media_note}\n{data.get('broadcast_body','') or 'Media xabar'}\n\nYuborishni tasdiqlaysizmi?", reply_markup=builder.as_markup())


async def _broadcast_worker(bot, repo, runtime, broadcast_id: int, body: str, segment: str, status_message, source_chat_id: int | None = None, source_message_id: int | None = None) -> None:
    if await repo.get_setting("broadcast_paused", "false") == "true":
        await repo.execute("UPDATE broadcasts SET status='paused' WHERE id=$1", broadcast_id)
        await status_message.edit_text("⛔ Broadcast xavfsizlik sozlamasi orqali to‘xtatilgan.", reply_markup=keyboards.back_home("adm:broadcast"))
        return
    conditions = {
        "all": "is_banned=FALSE AND blocked_bot=FALSE",
        "active": "is_banned=FALSE AND blocked_bot=FALSE AND last_seen >= NOW()-INTERVAL '7 days'",
        "new": "is_banned=FALSE AND blocked_bot=FALSE AND joined_at >= NOW()-INTERVAL '7 days'",
        "inactive": "is_banned=FALSE AND blocked_bot=FALSE AND last_seen < NOW()-INTERVAL '30 days'",
    }
    users = await repo.fetch(f"SELECT id FROM users WHERE {conditions[segment]} ORDER BY id")
    total = len(users)
    sent = failed = blocked = 0
    await repo.execute("UPDATE broadcasts SET total=$1,status='running' WHERE id=$2", total, broadcast_id)
    for index, user in enumerate(users, start=1):
        if await runtime.get(f"broadcast:cancel:{broadcast_id}") == "1" or await repo.get_setting("broadcast_paused", "false") == "true":
            break
        try:
            if source_chat_id and source_message_id:
                await bot.copy_message(user["id"], source_chat_id, source_message_id)
            else:
                await bot.send_message(user["id"], body)
            sent += 1
        except TelegramForbiddenError:
            blocked += 1
            await repo.execute("UPDATE users SET blocked_bot=TRUE WHERE id=$1", user["id"])
        except TelegramRetryAfter as exc:
            await asyncio.sleep(exc.retry_after + 0.2)
            try:
                if source_chat_id and source_message_id:
                    await bot.copy_message(user["id"], source_chat_id, source_message_id)
                else:
                    await bot.send_message(user["id"], body)
                sent += 1
            except TelegramForbiddenError:
                blocked += 1
                await repo.execute("UPDATE users SET blocked_bot=TRUE WHERE id=$1", user["id"])
            except TelegramAPIError:
                failed += 1
        except TelegramAPIError:
            failed += 1
        if index % 20 == 0:
            await repo.execute("UPDATE broadcasts SET sent=$1,failed=$2,blocked=$3 WHERE id=$4", sent, failed, blocked, broadcast_id)
            try:
                await status_message.edit_text(f"📣 <b>Broadcast bajarilmoqda</b>\n\n▓▓▓▓░░░░░░ {index}/{total}\n✅ {sent} · 🔴 {failed} · 🚫 {blocked}", reply_markup=keyboards._kb([[ ("⛔ Bekor qilish", f"broadcast:cancel:{broadcast_id}") ]]))
            except Exception:
                pass
        await asyncio.sleep(0.045)
    cancelled = await runtime.get(f"broadcast:cancel:{broadcast_id}") == "1"
    paused = await repo.get_setting("broadcast_paused", "false") == "true"
    state = "cancelled" if cancelled else ("paused" if paused else "completed")
    await repo.execute("UPDATE broadcasts SET sent=$1,failed=$2,blocked=$3,status=$4 WHERE id=$5", sent, failed, blocked, state, broadcast_id)
    try:
        await status_message.edit_text(f"{terminal_header('broadcast result')}\n\n{'🟡 Bekor qilindi' if cancelled else ('⛔ Pauza qilindi' if paused else '🟢 Yakunlandi')}\nJami: <b>{total}</b>\nYuborildi: <b>{sent}</b>\nXatolik: <b>{failed}</b>\nBloklangan: <b>{blocked}</b>", reply_markup=keyboards.back_home("adm:broadcast"))
    except Exception:
        pass


async def _run_broadcast_safely(bot, repo, runtime, broadcast_id: int, body: str, segment: str, status_message, source_chat_id: int | None, source_message_id: int | None, admin_id: int) -> None:
    """Keep detached broadcast task failures visible and persisted."""
    try:
        await _broadcast_worker(bot, repo, runtime, broadcast_id, body, segment, status_message, source_chat_id, source_message_id)
    except Exception as exc:
        logging.exception("Broadcast worker failed for id=%s", broadcast_id)
        try:
            await repo.execute("UPDATE broadcasts SET status='failed' WHERE id=$1", broadcast_id)
        except Exception:
            logging.exception("Could not persist failed broadcast state")
        try:
            await status_message.edit_text("🔴 <b>Broadcast kutilmagan xato bilan to‘xtadi.</b> Audit/log va ma’lumotlar bazasini tekshiring.", reply_markup=keyboards.back_home("adm:broadcast"))
        except Exception:
            pass
        try:
            await bot.send_message(admin_id, f"🔴 Broadcast #{broadcast_id} xatosi: {html.escape(str(exc)[:300])}")
        except Exception:
            pass


@router.callback_query(F.data == "broadcast:confirm")
async def confirm_broadcast(callback: CallbackQuery, state: FSMContext, repo, runtime) -> None:
    if not await admin_callback_guard(callback): return
    data = await state.get_data()
    body, segment = data.get("broadcast_body"), data.get("broadcast_segment")
    has_media = bool(data.get("broadcast_source_chat_id") and data.get("broadcast_source_message_id"))
    if (not body and not has_media) or not segment:
        await callback.answer("Broadcast ma’lumotlari topilmadi.", show_alert=True); return
    await callback.answer("Broadcast boshlandi.")
    row = await repo.fetchrow("INSERT INTO broadcasts(body,segment,status,source_chat_id,source_message_id) VALUES($1,$2,'pending',$3,$4) RETURNING id", body, segment, data.get('broadcast_source_chat_id'), data.get('broadcast_source_message_id'))
    broadcast_id = int(row["id"])
    await state.clear()
    if callback.message:
        status = await callback.message.edit_text("📣 Broadcast navbatga olindi...")
        asyncio.create_task(_run_broadcast_safely(callback.bot, repo, runtime, broadcast_id, body, segment, status, data.get('broadcast_source_chat_id'), data.get('broadcast_source_message_id'), callback.from_user.id))


@router.callback_query(F.data.startswith("broadcast:cancel:"))
async def cancel_broadcast(callback: CallbackQuery, runtime) -> None:
    if not await admin_callback_guard(callback): return
    broadcast_id = int((callback.data or "broadcast:cancel:0").split(":")[-1])
    await runtime.set(f"broadcast:cancel:{broadcast_id}", "1", ttl=3600)
    await callback.answer("Bekor qilish so‘rovi yuborildi.")
