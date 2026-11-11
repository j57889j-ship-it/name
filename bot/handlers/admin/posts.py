"""AI-powered Telegram channel post writer and publisher."""
from __future__ import annotations
import html
import re
from datetime import datetime
from zoneinfo import ZoneInfo
from aiogram import Router, F
from aiogram.types import CallbackQuery, Message
from aiogram.fsm.context import FSMContext
from bot.config import settings
from bot.middlewares.admin_only import AdminFilter
from bot.handlers.common import admin_callback_guard
from bot.states import AdminStates
from bot.ui import keyboards
from bot.ui.theme import terminal_header
from bot.services.ai_service import AIService
from bot.services.post_service import clean_telegram_html
from bot.ui.stylizer import render_post

router = Router(name="admin-post-writer")
router.message.filter(AdminFilter())
router.callback_query.filter(AdminFilter())


def _post_system() -> str:
    return (settings.project_root / "bot" / "prompts" / "post_writer.txt").read_text(encoding="utf-8")


def _variants(raw: str) -> list[str]:
    matches = re.split(r"\[VARIANT\s*[123]\]", raw, flags=re.I)
    values = [clean_telegram_html(x) for x in matches if x.strip()]
    if len(values) >= 3:
        return values[:3]
    # Fallback for providers that return numbered variants without exact markers.
    parts = re.split(r"(?:^|\n)\s*(?:[1-3][.)]|Variant\s*[1-3])\s*", raw, flags=re.I)
    values = [clean_telegram_html(x) for x in parts if x.strip()]
    if len(values) >= 3:
        return values[:3]
    return [clean_telegram_html(raw)] * 3


async def _generate_variants(admin_id: int, topic: str, message: Message, state: FSMContext, ai_service: AIService) -> None:
    loading_message = await message.answer("🛰 <b>Kontent generator ishga tushdi...</b>")
    from bot.ui.fx import loading as loading_animation
    import asyncio
    effects = await ai_service.repo.get_setting("effects_enabled", "true") == "true"
    animation_task = asyncio.create_task(loading_animation(loading_message, effects, "post variantlari tuzilmoqda"))
    try:
        result = await ai_service.generate(admin_id, "channel_post", _post_system(), topic, temperature=0.85, max_tokens=2200)
        animation_task.cancel()
        await asyncio.gather(animation_task, return_exceptions=True)
        variants = _variants(result.text)
        await state.update_data(post_topic=topic, post_variants=variants, post_index=0, post_body=variants[0], post_id=None)
        text = f"{terminal_header('content studio')}\n\n🧠 <b>3 ta post varianti tayyor.</b>\n\n{variants[0][:3500]}"
        await loading_message.edit_text(text, reply_markup=keyboards.post_variants())
    except Exception as exc:
        animation_task.cancel()
        await asyncio.gather(animation_task, return_exceptions=True)
        await loading_message.edit_text(f"🔴 <b>Post yaratilmadi:</b> {html.escape(str(exc)[:400])}", reply_markup=keyboards.back_home("adm:home"))


@router.callback_query(F.data == "adm:posts")
async def post_menu(callback: CallbackQuery, state: FSMContext) -> None:
    if not await admin_callback_guard(callback): return
    await callback.answer()
    await state.clear()
    await state.set_state(AdminStates.waiting_post_topic)
    if callback.message:
        await callback.message.edit_text(
            f"{terminal_header('content studio')}\n\n✍️ Post mavzusini, tayyor matnni yoki foto bilan caption yuboring.\n\nAI 3 xil variant tayyorlaydi.",
            reply_markup=keyboards.back_home("adm:home"),
        )


@router.message(AdminStates.waiting_post_topic)
async def topic_input(message: Message, state: FSMContext, ai_service: AIService) -> None:
    topic = (message.text or message.caption or "").strip()
    if not topic or len(topic) > 3000:
        await message.answer("⚠️ Mavzu yoki matn 1–3000 belgi bo‘lishi kerak.")
        return
    media_type = None
    media_file_id = None
    if message.photo:
        media_type, media_file_id = 'photo', message.photo[-1].file_id
    elif message.video:
        media_type, media_file_id = 'video', message.video.file_id
    elif message.document:
        media_type, media_file_id = 'document', message.document.file_id
    elif message.animation:
        media_type, media_file_id = 'animation', message.animation.file_id
    elif message.audio:
        media_type, media_file_id = 'audio', message.audio.file_id
    elif message.voice:
        media_type, media_file_id = 'voice', message.voice.file_id
    await state.update_data(post_topic=topic, post_media_type=media_type, post_media_file_id=media_file_id)
    await _generate_variants(message.from_user.id, topic, message, state, ai_service)


@router.callback_query(F.data.startswith("post:variant:"))
async def choose_variant(callback: CallbackQuery, state: FSMContext, repo) -> None:
    if not await admin_callback_guard(callback): return
    index = int((callback.data or "post:variant:0").split(":")[-1])
    data = await state.get_data()
    variants = data.get("post_variants", [])
    if index not in range(len(variants)):
        await callback.answer("Variant eskirgan.", show_alert=True)
        return
    await callback.answer()
    body = variants[index]
    style = await repo.get_setting("default_post_style", "terminal")
    font = await repo.get_setting("default_post_font", "bold")
    post_id = await repo.save_post(data.get("post_topic", "Yangi post")[:180], body, callback.from_user.id, style, font, data.get("post_media_type"), data.get("post_media_file_id"))
    await state.update_data(post_index=index, post_body=body, post_id=post_id)
    preview = clean_telegram_html(render_post(body, style, font))
    if callback.message:
        await callback.message.edit_text(
            f"{terminal_header('post preview')}\n\n{('🖼 Media biriktirilgan: ' + str(data.get('post_media_type')) + '\n\n') if data.get('post_media_type') else ''}{preview[:3200]}\n\n<code>POST ID: {post_id}  •  BODY LENGTH: {len(body)}</code>",
            reply_markup=keyboards.post_preview(),
        )


@router.callback_query(F.data == "post:publish")
async def publish_post(callback: CallbackQuery, state: FSMContext, post_service, repo) -> None:
    if not await admin_callback_guard(callback): return
    data = await state.get_data()
    post_id = data.get("post_id")
    if not post_id:
        await callback.answer("Avval variant tanlang.", show_alert=True)
        return
    await callback.answer()
    try:
        message_id = await post_service.publish(int(post_id))
        await repo.audit(callback.from_user.id, "post_published", {"post_id": post_id, "message_id": message_id})
        if callback.message:
            from bot.ui.fx import success_stamp
            effects = await repo.get_setting("effects_enabled", "true") == "true"
            await success_stamp(callback.message, f"Post kanalga joylandi. POST ID: {post_id}", effects, keyboards.back_home())
    except Exception as exc:
        if callback.message:
            from bot.ui.fx import failure_stamp
            effects = await repo.get_setting("effects_enabled", "true") == "true"
            await failure_stamp(callback.message, f"Nashr xatosi: {str(exc)[:400]}", effects, keyboards.back_home())


@router.callback_query(F.data == "post:schedule")
async def schedule_start(callback: CallbackQuery, state: FSMContext) -> None:
    if not await admin_callback_guard(callback): return
    data = await state.get_data()
    if not data.get("post_id"):
        await callback.answer("Avval post variantini tanlang.", show_alert=True)
        return
    await callback.answer()
    from aiogram.utils.keyboard import InlineKeyboardBuilder
    builder = InlineKeyboardBuilder()
    builder.button(text="Bir martalik", callback_data="post:recurrence:once")
    builder.button(text="Har kuni", callback_data="post:recurrence:daily")
    for day, title in [("mon","Du"),("tue","Se"),("wed","Ch"),("thu","Pa"),("fri","Ju"),("sat","Sh"),("sun","Ya")]:
        builder.button(text=f"Haftalik · {title}", callback_data=f"post:recurrence:weekly:{day}")
    builder.adjust(2, 4, 3)
    if callback.message:
        await callback.message.answer("🕒 Rejalashtirish turini tanlang:", reply_markup=builder.as_markup())


@router.callback_query(F.data.startswith("post:recurrence:"))
async def choose_recurrence(callback: CallbackQuery, state: FSMContext) -> None:
    if not await admin_callback_guard(callback): return
    parts = (callback.data or "").split(":")
    recurrence = ":".join(parts[2:])
    if recurrence not in {"once", "daily", "weekly:mon", "weekly:tue", "weekly:wed", "weekly:thu", "weekly:fri", "weekly:sat", "weekly:sun"}:
        await callback.answer("Takrorlanish turi noto‘g‘ri.", show_alert=True); return
    await state.update_data(schedule_recurrence=recurrence)
    await state.set_state(AdminStates.waiting_schedule_time)
    await callback.answer()
    if callback.message:
        await callback.message.edit_text("🕒 Boshlanish sanasi va vaqtini yuboring: <code>2026-12-01 18:30</code> (Toshkent vaqti). Takroriy rejada shu vaqt har safar ishlatiladi.")


@router.message(AdminStates.waiting_schedule_time)
async def schedule_time_input(message: Message, state: FSMContext, scheduler_service, repo) -> None:
    value = (message.text or "").strip()
    try:
        run_at = datetime.strptime(value, "%Y-%m-%d %H:%M").replace(tzinfo=ZoneInfo(settings.timezone))
        if run_at <= datetime.now(ZoneInfo(settings.timezone)):
            raise ValueError("Vaqt kelajakda bo‘lishi kerak")
    except ValueError as exc:
        await message.answer(f"⚠️ Sana formati noto‘g‘ri yoki vaqt o‘tib ketgan. {html.escape(str(exc))}")
        return
    data = await state.get_data()
    post_id = data.get("post_id")
    if not post_id:
        await message.answer("Post topilmadi. Qaytadan yarating.")
        await state.clear()
        return
    job_id = await scheduler_service.schedule_post(int(post_id), run_at, data.get("schedule_recurrence", "once"))
    await repo.audit(message.from_user.id, "post_scheduled", {"post_id": post_id, "job_id": job_id})
    await state.clear()
    await message.answer(f"🟢 Post {run_at:%Y-%m-%d %H:%M} vaqtiga rejalashtirildi.\n<code>JOB #{job_id}</code>", reply_markup=keyboards.admin_home())


@router.callback_query(F.data.startswith("post:style:"))
async def select_post_style(callback: CallbackQuery, state: FSMContext, repo) -> None:
    if not await admin_callback_guard(callback): return
    style = (callback.data or "").split(":")[-1]
    if style not in {"terminal", "card", "minimal", "script"}:
        await callback.answer("Uslub topilmadi.", show_alert=True); return
    data = await state.get_data()
    post_id = data.get("post_id")
    if not post_id:
        await callback.answer("Avval variant tanlang.", show_alert=True); return
    await repo.execute("UPDATE posts SET style=$1 WHERE id=$2 AND status='draft'", style, int(post_id))
    post = await repo.get_post(int(post_id))
    preview = clean_telegram_html(render_post(post["body_html"], style, post["font"]))
    await callback.answer(f"Uslub: {style}")
    if callback.message:
        await callback.message.edit_text(f"{terminal_header('post preview')}\n\n{preview[:3400]}\n\n<code>STYLE: {style}  •  FONT: {post['font']}</code>", reply_markup=keyboards.post_preview())


@router.callback_query(F.data.startswith("post:font:"))
async def select_post_font(callback: CallbackQuery, state: FSMContext, repo) -> None:
    if not await admin_callback_guard(callback): return
    font = (callback.data or "").split(":")[-1]
    if font not in {"bold", "sans", "bolditalic", "script", "mono", "smallcaps"}:
        await callback.answer("Shrift topilmadi.", show_alert=True); return
    data = await state.get_data()
    post_id = data.get("post_id")
    if not post_id:
        await callback.answer("Avval variant tanlang.", show_alert=True); return
    await repo.execute("UPDATE posts SET font=$1 WHERE id=$2 AND status='draft'", font, int(post_id))
    post = await repo.get_post(int(post_id))
    preview = clean_telegram_html(render_post(post["body_html"], post["style"], font))
    await callback.answer(f"Shrift: {font}")
    if callback.message:
        await callback.message.edit_text(f"{terminal_header('post preview')}\n\n{preview[:3400]}\n\n<code>STYLE: {post['style']}  •  FONT: {font}</code>", reply_markup=keyboards.post_preview())


@router.callback_query(F.data == "post:edit")
async def edit_post_start(callback: CallbackQuery, state: FSMContext) -> None:
    if not await admin_callback_guard(callback): return
    await callback.answer()
    await state.set_state(AdminStates.waiting_post_edit)
    if callback.message:
        await callback.message.answer("✏️ Yangi post matnini yuboring. HTML formatlash ruxsat etilgan teglar bilan tozalanadi.")


@router.message(AdminStates.waiting_post_edit)
async def edit_post_input(message: Message, state: FSMContext, repo) -> None:
    body = clean_telegram_html(message.text or message.caption or "")
    if not body or len(body) > 4096:
        await message.answer("⚠️ Matn bo‘sh yoki Telegram 4096 belgilik chegarasidan katta.")
        return
    data = await state.get_data()
    post_id = data.get("post_id")
    if post_id:
        await repo.execute("UPDATE posts SET body_html=$1 WHERE id=$2 AND status='draft'", body, int(post_id))
    else:
        post_id = await repo.save_post("Tahrirlangan post", body, message.from_user.id)
    await state.update_data(post_id=int(post_id), post_body=body)
    await state.set_state(None)
    current = await repo.get_post(int(post_id))
    preview = clean_telegram_html(render_post(body, current["style"], current["font"])) if current else body
    await message.answer(f"{terminal_header('edited preview')}\n\n{preview}\n\n<code>POST ID: {post_id}</code>", reply_markup=keyboards.post_preview())


@router.callback_query(F.data == "post:rewrite")
async def rewrite_post(callback: CallbackQuery, state: FSMContext, ai_service: AIService) -> None:
    if not await admin_callback_guard(callback): return
    await callback.answer()
    data = await state.get_data()
    topic = data.get("post_topic")
    if callback.message and topic:
        await _generate_variants(callback.from_user.id, topic, callback.message, state, ai_service)
    elif callback.message:
        await callback.message.answer("Avval mavzu kiriting.", reply_markup=keyboards.back_home("adm:posts"))


@router.callback_query(F.data == "post:cancel")
async def cancel_post(callback: CallbackQuery, state: FSMContext) -> None:
    if not await admin_callback_guard(callback): return
    await callback.answer("Qoralama bekor qilindi.")
    await state.clear()
    if callback.message:
        await callback.message.edit_text("🟡 Post tayyorlash bekor qilindi.", reply_markup=keyboards.back_home())
