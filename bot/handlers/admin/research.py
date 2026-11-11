"""Admin-only live research and Uzbek summary generation."""
from __future__ import annotations
import html
import json
from aiogram import Router, F
from aiogram.types import CallbackQuery, Message
from aiogram.fsm.context import FSMContext
from bot.middlewares.admin_only import AdminFilter
from bot.handlers.common import admin_callback_guard
from bot.states import AdminStates
from bot.services.ai_service import AIService
from bot.services.research_service import ResearchService
from bot.ui import keyboards
from bot.ui.theme import terminal_header

router = Router(name="admin-research")
router.callback_query.filter(AdminFilter())
router.message.filter(AdminFilter())


@router.callback_query(F.data == "adm:research")
async def research_menu(callback: CallbackQuery, state: FSMContext) -> None:
    if not await admin_callback_guard(callback): return
    await callback.answer()
    await state.set_state(AdminStates.waiting_ai_research)
    if callback.message:
        await callback.message.edit_text(f"{terminal_header('ai research center')}\n\n🛰 Qaysi dasturlash yoki AI mavzusini tadqiq qilamiz?\nMisol: 2026-yildagi yangi Python kutubxonalari.", reply_markup=keyboards.back_home())


@router.message(AdminStates.waiting_ai_research)
async def research_query(message: Message, state: FSMContext, ai_service: AIService) -> None:
    query = (message.text or "").strip()
    if not query or len(query) > 300:
        await message.answer("Mavzu 1–300 belgi bo‘lishi kerak.")
        return
    status = await message.answer("🛰 Ochiq manbalar qidirilmoqda...")
    try:
        results = await ResearchService().search(query, 6)
        result = await ai_service.generate(
            message.from_user.id, "research_summary",
            "Siz texnologik tadqiqotchisiz. Faqat berilgan manbalardan foydalaning. O'zbek lotinida qisqa tahlil, 5 ta fakt va tekshiruvda qolgan savollarni yozing. Har bir fakt uchun manba URLini ko'rsating. Manbalarda yo'q faktni qo'shmang.",
            json.dumps(results, ensure_ascii=False), max_tokens=2200,
        )
        links = "\n\n<b>Manbalar:</b>\n" + "\n".join(f"• <a href=\"{html.escape(x['url'], quote=True)}\">{html.escape(x['title'][:100])}</a>" for x in results if x.get("url"))
        await status.edit_text(f"{terminal_header('research report')}\n\n{html.escape(result.text)[:3000]}{links}", reply_markup=keyboards.back_home("adm:research"), disable_web_page_preview=True)
        await state.clear()
    except Exception as exc:
        await status.edit_text(f"🔴 Research bajarilmadi: {html.escape(str(exc)[:350])}\nTavily API kaliti sozlanganini tekshiring.", reply_markup=keyboards.back_home())
