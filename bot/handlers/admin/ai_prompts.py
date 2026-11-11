"""Admin-only prompt engineering studio and prompt library."""
from __future__ import annotations
import html
from pathlib import Path
from aiogram import Router, F
from aiogram.types import CallbackQuery, Message
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.fsm.context import FSMContext
from bot.middlewares.admin_only import AdminFilter
from bot.handlers.common import admin_callback_guard
from bot.states import AdminStates
from bot.ui import keyboards
from bot.ui.theme import terminal_header
from bot.services.ai_service import AIService
from bot.config import settings

router = Router(name="admin-ai-prompts")
router.message.filter(AdminFilter())
router.callback_query.filter(AdminFilter())

CATEGORIES = {"code": "💻 Kod", "text": "✍️ Matn", "image": "🎨 Rasm", "business": "📊 Biznes", "study": "🎓 O‘qish", "other": "🧩 Boshqa"}


def _system_prompt() -> str:
    return (settings.project_root / "bot" / "prompts" / "prompt_engineer.txt").read_text(encoding="utf-8")


async def _generate_prompt(admin_id: int, state: FSMContext, message: Message, service: AIService, operation: str = "generate") -> None:
    data = await state.get_data()
    task = data.get("prompt_task", "")
    current = data.get("current_prompt", "")
    system = _system_prompt()
    user = f"Kategoriya: {CATEGORIES.get(data.get('prompt_category'), 'Boshqa')}\nVazifa: {task}"
    if operation == "improve":
        user = f"Quyidagi promptni kuchaytiring va aniqlashtiring:\n{current}\n\nOxirida 3 ta qisqa yaxshilanish izohini bering."
    elif operation == "shorten":
        user = f"Quyidagi promptni vazifasini yo'qotmasdan ixchamlashtiring:\n{current}"
    elif operation == "english":
        user = f"Quyidagi promptni professional ingliz tiliga tarjima qiling. Tuzilmani saqlang:\n{current}"
    progress = await message.answer("⠋ <b>AI core ishga tushmoqda...</b>")
    import asyncio
    from bot.ui.fx import loading
    animation_task = asyncio.create_task(
        loading(progress, await service.repo.get_setting("effects_enabled", "true") == "true", "prompt matrix qayta ishlanmoqda")
    )
    try:
        result = await service.generate(admin_id, f"prompt_{operation}", system, user, temperature=0.65, max_tokens=2600)
        animation_task.cancel()
        await asyncio.gather(animation_task, return_exceptions=True)
        prompt = result.text.strip()
        await state.update_data(current_prompt=prompt)
        display = prompt[:3500]
        suffix = "\n… [matnning qolgan qismi kutubxonaga saqlanishi mumkin]" if len(prompt) > 3500 else ""
        from bot.ui.fx import typewriter_reveal
        effects = await service.repo.get_setting("effects_enabled", "true") == "true"
        await typewriter_reveal(
            progress, "🧠 TAYYOR PROMPT\n\n" + display + suffix,
            enabled=effects, reply_markup=keyboards.prompt_actions(),
        )
    except Exception as exc:
        animation_task.cancel()
        await asyncio.gather(animation_task, return_exceptions=True)
        await progress.edit_text(f"🔴 <b>AI xatosi:</b> {html.escape(str(exc)[:500])}", reply_markup=keyboards.back_home("adm:ai"))


@router.callback_query(F.data == "adm:ai")
async def prompt_menu(callback: CallbackQuery, state: FSMContext) -> None:
    if not await admin_callback_guard(callback): return
    await callback.answer()
    await state.clear()
    if callback.message:
        await callback.message.edit_text(
            f"{terminal_header('ai prompt studio')}\n\n🧠 <b>Prompt kategoriyasini tanlang.</b>",
            reply_markup=keyboards.categories(),
        )


@router.callback_query(F.data.startswith("ai:cat:"))
async def select_category(callback: CallbackQuery, state: FSMContext) -> None:
    if not await admin_callback_guard(callback): return
    await callback.answer()
    category = (callback.data or "").split(":")[-1]
    if category not in CATEGORIES:
        return
    await state.clear()
    await state.update_data(prompt_category=category)
    await state.set_state(AdminStates.waiting_prompt_task)
    if callback.message:
        await callback.message.edit_text(
            f"{terminal_header('prompt input')}\n\n✍️ <b>{CATEGORIES[category]}</b> kategoriyasi uchun vazifani yozing.\n\nMasalan: Python'da Telegram bot uchun xavfsiz login prompti yarat.",
            reply_markup=keyboards.back_home("adm:ai"),
        )


@router.message(AdminStates.waiting_prompt_task)
async def prompt_task_input(message: Message, state: FSMContext, ai_service: AIService) -> None:
    task = (message.text or message.caption or "").strip()
    if not task or len(task) > 2500:
        await message.answer("⚠️ Vazifa 1–2500 belgi bo‘lishi kerak.")
        return
    await state.update_data(prompt_task=task)
    await _generate_prompt(message.from_user.id, state, message, ai_service)


@router.callback_query(F.data.in_({"ai:again", "ai:improve", "ai:shorten", "ai:english"}))
async def prompt_transform(callback: CallbackQuery, state: FSMContext, ai_service: AIService) -> None:
    if not await admin_callback_guard(callback): return
    await callback.answer()
    action = (callback.data or "ai:again").split(":")[1]
    if callback.message:
        if action == "again":
            data = await state.get_data()
            if not data.get("prompt_task"):
                await callback.message.answer("Avval vazifani kiriting.", reply_markup=keyboards.categories())
                return
            await _generate_prompt(callback.from_user.id, state, callback.message, ai_service)
        else:
            await _generate_prompt(callback.from_user.id, state, callback.message, ai_service, operation=action)


@router.callback_query(F.data == "ai:save")
async def save_prompt_start(callback: CallbackQuery, state: FSMContext) -> None:
    if not await admin_callback_guard(callback): return
    data = await state.get_data()
    if not data.get("current_prompt"):
        await callback.answer("Saqlash uchun prompt yo‘q.", show_alert=True)
        return
    await callback.answer()
    await state.set_state(AdminStates.waiting_prompt_title)
    if callback.message:
        await callback.message.answer("💾 Prompt uchun nom yuboring:")


@router.message(AdminStates.waiting_prompt_title)
async def save_prompt_title(message: Message, state: FSMContext, repo) -> None:
    title = (message.text or "").strip()
    data = await state.get_data()
    if not title or len(title) > 120:
        await message.answer("Nom 1–120 belgi bo‘lishi kerak.")
        return
    prompt_id = await repo.save_prompt(title, CATEGORIES.get(data.get("prompt_category"), "Boshqa"), data.get("current_prompt", ""), message.from_user.id)
    await repo.audit(message.from_user.id, "prompt_saved", {"prompt_id": prompt_id})
    await state.set_state(None)
    await message.answer(f"🟢 Prompt #{prompt_id} kutubxonaga saqlandi.", reply_markup=keyboards.prompt_actions(prompt_id))


@router.callback_query(F.data == "ai:publish")
async def prompt_to_channel(callback: CallbackQuery, state: FSMContext, repo) -> None:
    if not await admin_callback_guard(callback): return
    data = await state.get_data()
    prompt = (data.get("current_prompt") or "").strip()
    if not prompt:
        await callback.answer("Avval prompt yarating.", show_alert=True)
        return
    await callback.answer()
    body = "<b>🧠 FOYDALI PROMPT</b>\n\n<pre>" + html.escape(prompt[:3000]) + "</pre>\n\n#prompt #ai #dasturlash"
    style = await repo.get_setting("default_post_style", "terminal")
    font = await repo.get_setting("default_post_font", "bold")
    post_id = await repo.save_post("AI prompt", body, callback.from_user.id, style, font)
    await state.update_data(post_id=post_id, post_body=body, post_topic="AI prompt")
    from bot.ui.stylizer import render_post
    from bot.services.post_service import clean_telegram_html
    preview = clean_telegram_html(render_post(body, style, font))
    if callback.message:
        await callback.message.edit_text(
            f"{terminal_header('prompt post preview')}\n\n{preview}\n\n<code>POST ID: {post_id}</code>",
            reply_markup=keyboards.post_preview(),
        )


@router.callback_query(F.data == "ai:library")
async def prompt_library(callback: CallbackQuery, repo) -> None:
    if not await admin_callback_guard(callback): return
    await callback.answer()
    rows = await repo.list_prompts(10, 0)
    builder = InlineKeyboardBuilder()
    for row in rows:
        icon = "⭐" if row["is_favorite"] else "🧠"
        builder.button(text=f"{icon} {str(row['title'])[:35]}", callback_data=f"ai:open:{row['id']}")
    builder.adjust(1)
    builder.row(keyboards.__button("🔎 Qidirish", "ai:search"))
    builder.row(keyboards.__button("🏠 Menyu", "adm:home"))
    text = f"{terminal_header('prompt library')}\n\n📚 <b>Saqlangan promptlar</b>\nJami ko‘rsatilmoqda: <b>{len(rows)}</b>"
    if not rows:
        text += "\n\nKutubxona hozircha bo‘sh."
    if callback.message:
        await callback.message.edit_text(text, reply_markup=builder.as_markup())


@router.callback_query(F.data.startswith("ai:open:"))
async def prompt_open(callback: CallbackQuery, state: FSMContext, repo) -> None:
    if not await admin_callback_guard(callback): return
    prompt_id = int((callback.data or "ai:open:0").split(":")[-1])
    row = await repo.get_prompt(prompt_id)
    if not row:
        await callback.answer("Prompt topilmadi.", show_alert=True)
        return
    await callback.answer()
    await state.update_data(current_prompt=row["body"], prompt_category=row["category"], selected_prompt_id=prompt_id)
    builder = InlineKeyboardBuilder()
    builder.button(text="📢 Kanalga post qilish", callback_data="ai:publish")
    builder.button(text="⭐ Sevimli / olib tashlash", callback_data=f"ai:fav:{prompt_id}")
    builder.button(text="✏️ Nomini o‘zgartirish", callback_data=f"ai:rename:{prompt_id}")
    builder.button(text="🗑 O‘chirish", callback_data=f"ai:delete:{prompt_id}")
    builder.adjust(1)
    builder.row(keyboards.__button("⬅️ Kutubxona", "ai:library"), keyboards.__button("🏠 Menyu", "adm:home"))
    body = str(row["body"])
    await callback.message.edit_text(
        f"{terminal_header('saved prompt')}\n\n<b>{html.escape(row['title'])}</b> · {html.escape(row['category'])}\n\n<pre>{html.escape(body[:3300])}</pre>",
        reply_markup=builder.as_markup(),
    )


@router.callback_query(F.data.startswith("ai:fav:"))
async def prompt_favorite(callback: CallbackQuery, repo) -> None:
    if not await admin_callback_guard(callback): return
    prompt_id = int((callback.data or "ai:fav:0").split(":")[-1])
    row = await repo.get_prompt(prompt_id)
    if not row:
        await callback.answer("Prompt topilmadi.", show_alert=True)
        return
    await repo.execute("UPDATE prompts SET is_favorite=NOT is_favorite WHERE id=$1", prompt_id)
    await repo.audit(callback.from_user.id, "prompt_favorite_toggled", {"prompt_id": prompt_id})
    await callback.answer("Sevimlilar holati o‘zgartirildi.")
    if callback.message:
        await prompt_open_refresh(callback.message, repo, prompt_id)


async def prompt_open_refresh(message, repo, prompt_id: int) -> None:
    row = await repo.get_prompt(prompt_id)
    if not row:
        await message.edit_text("Prompt topilmadi.", reply_markup=keyboards.back_home("adm:ai"))
        return
    builder = InlineKeyboardBuilder()
    builder.button(text="📢 Kanalga post qilish", callback_data="ai:publish")
    builder.button(text="⭐ Sevimli / olib tashlash", callback_data=f"ai:fav:{prompt_id}")
    builder.button(text="✏️ Nomini o‘zgartirish", callback_data=f"ai:rename:{prompt_id}")
    builder.button(text="🗑 O‘chirish", callback_data=f"ai:delete:{prompt_id}")
    builder.adjust(1)
    builder.row(keyboards.__button("⬅️ Kutubxona", "ai:library"), keyboards.__button("🏠 Menyu", "adm:home"))
    await message.edit_text(
        f"{terminal_header('saved prompt')}\n\n{'⭐ ' if row['is_favorite'] else ''}<b>{html.escape(row['title'])}</b> · {html.escape(row['category'])}\n\n<pre>{html.escape(str(row['body'])[:3300])}</pre>",
        reply_markup=builder.as_markup(),
    )


@router.callback_query(F.data.startswith("ai:rename:"))
async def prompt_rename_start(callback: CallbackQuery, state: FSMContext, repo) -> None:
    if not await admin_callback_guard(callback): return
    prompt_id = int((callback.data or "ai:rename:0").split(":")[-1])
    row = await repo.get_prompt(prompt_id)
    if not row:
        await callback.answer("Prompt topilmadi.", show_alert=True)
        return
    await callback.answer()
    await state.update_data(rename_prompt_id=prompt_id)
    await state.set_state(AdminStates.waiting_prompt_rename)
    if callback.message:
        await callback.message.edit_text(f"✏️ <b>{html.escape(row['title'])}</b> uchun yangi nom yuboring (1–120 belgi).")


@router.message(AdminStates.waiting_prompt_rename)
async def prompt_rename_save(message: Message, state: FSMContext, repo) -> None:
    title = (message.text or "").strip()
    if not title or len(title) > 120:
        await message.answer("Nom 1–120 belgi bo‘lishi kerak.")
        return
    data = await state.get_data()
    prompt_id = int(data.get("rename_prompt_id", 0))
    await repo.execute("UPDATE prompts SET title=$1 WHERE id=$2", title, prompt_id)
    await repo.audit(message.from_user.id, "prompt_renamed", {"prompt_id": prompt_id})
    await state.clear()
    await message.answer("🟢 Prompt nomi yangilandi.", reply_markup=keyboards.back_home("adm:ai"))


@router.callback_query(F.data.startswith("ai:delete:"))
async def prompt_delete_confirm(callback: CallbackQuery, repo) -> None:
    if not await admin_callback_guard(callback): return
    prompt_id = int((callback.data or "ai:delete:0").split(":")[-1])
    if not await repo.get_prompt(prompt_id):
        await callback.answer("Prompt topilmadi.", show_alert=True)
        return
    await callback.answer()
    builder = InlineKeyboardBuilder()
    builder.button(text="🗑 Ha, o‘chirilsin", callback_data=f"ai:deleteconfirm:{prompt_id}")
    builder.button(text="⬅️ Bekor qilish", callback_data=f"ai:open:{prompt_id}")
    builder.adjust(1)
    if callback.message:
        await callback.message.edit_text(f"⚠️ <b>#{prompt_id}</b> promptni butunlay o‘chirasizmi?", reply_markup=builder.as_markup())


@router.callback_query(F.data.startswith("ai:deleteconfirm:"))
async def prompt_delete(callback: CallbackQuery, repo) -> None:
    if not await admin_callback_guard(callback): return
    prompt_id = int((callback.data or "ai:deleteconfirm:0").split(":")[-1])
    await repo.execute("DELETE FROM prompts WHERE id=$1", prompt_id)
    await repo.audit(callback.from_user.id, "prompt_deleted", {"prompt_id": prompt_id})
    await callback.answer("Prompt o‘chirildi.")
    if callback.message:
        await callback.message.edit_text("🟢 Prompt o‘chirildi.", reply_markup=keyboards.back_home("adm:ai"))


@router.callback_query(F.data == "ai:search")
async def prompt_search_start(callback: CallbackQuery, state: FSMContext) -> None:
    if not await admin_callback_guard(callback): return
    await callback.answer()
    await state.set_state(AdminStates.waiting_prompt_search)
    if callback.message:
        await callback.message.edit_text("🔎 Prompt nomi, kategoriyasi yoki matnidan kalit so‘z yuboring:", reply_markup=keyboards.back_home("adm:ai"))


@router.message(AdminStates.waiting_prompt_search)
async def prompt_search_results(message: Message, state: FSMContext, repo) -> None:
    keyword = (message.text or "").strip()
    if not keyword or len(keyword) > 100:
        await message.answer("Qidiruv so‘rovi 1–100 belgi bo‘lishi kerak.")
        return
    rows = await repo.search_prompts(keyword, 10)
    builder = InlineKeyboardBuilder()
    for row in rows:
        builder.button(text=f"{'⭐' if row['is_favorite'] else '🧠'} {str(row['title'])[:35]}", callback_data=f"ai:open:{row['id']}")
    builder.adjust(1)
    builder.row(keyboards.__button("📚 Kutubxona", "ai:library"), keyboards.__button("🏠 Menyu", "adm:home"))
    await state.clear()
    label = "\n".join(f"• <b>{html.escape(row['title'])}</b> · {html.escape(row['category'])}" for row in rows) or "Natija topilmadi."
    await message.answer(f"{terminal_header('prompt search')}\n\n{label}", reply_markup=builder.as_markup())
