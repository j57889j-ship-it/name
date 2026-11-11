"""Admin analytics dashboard with in-memory charts and AI analysis."""
from __future__ import annotations
import json
import html
from aiogram import Router, F
from aiogram.types import CallbackQuery, BufferedInputFile
from bot.middlewares.admin_only import AdminFilter
from bot.handlers.common import admin_callback_guard
from bot.ui import keyboards
from bot.ui.theme import terminal_header
from bot.services.analytics_service import AnalyticsService
from bot.services.charts import growth_chart
from bot.services.ai_service import AIService

router = Router(name="admin-analytics")
router.callback_query.filter(AdminFilter())


@router.callback_query(F.data == "adm:analytics")
async def analytics_dashboard(callback: CallbackQuery, analytics_service: AnalyticsService) -> None:
    if not await admin_callback_guard(callback): return
    await callback.answer()
    stats = await analytics_service.dashboard()
    text = (
        f"{terminal_header('analytics dashboard')}\n\n"
        f"👥 Jami foydalanuvchilar: <b>{stats['users']}</b>\n"
        f"🆕 Bugungi yangi: <b>{stats['new_today']}</b>\n"
        f"💬 Ochiq murojaatlar: <b>{stats['open_tickets']}</b>\n"
        f"🕒 Rejalashtirilgan postlar: <b>{stats['scheduled_posts']}</b>\n"
        f"📢 Bugun joylangan postlar: <b>{stats['posts_today']}</b>\n\n"
        "Ko‘rsatkichlar bot va webhook orqali kuzatilgan hodisalarga asoslanadi."
    )
    from aiogram.utils.keyboard import InlineKeyboardBuilder
    builder = InlineKeyboardBuilder()
    builder.button(text="📈 30 kunlik o‘sish", callback_data="analytics:growth")
    builder.button(text="💬 Support hisoboti", callback_data="analytics:support")
    builder.button(text="🧠 AI tahlilchi", callback_data="analytics:ai")
    builder.adjust(1)
    builder.row(keyboards.__button("🏠 Bosh menyu", "adm:home"))
    if callback.message: await callback.message.edit_text(text, reply_markup=builder.as_markup())


@router.callback_query(F.data == "analytics:growth")
async def growth_report(callback: CallbackQuery, analytics_service: AnalyticsService) -> None:
    if not await admin_callback_guard(callback): return
    await callback.answer()
    rows = await analytics_service.user_growth()
    if not rows:
        if callback.message: await callback.message.edit_text("Hozircha o‘sish ma’lumoti yetarli emas.", reply_markup=keyboards.back_home("adm:analytics"))
        return
    image = await growth_chart(rows)
    if callback.message:
        await callback.message.answer_photo(BufferedInputFile(image.getvalue(), filename="growth.png"), caption="📈 <b>Oxirgi 30 kunlik yangi foydalanuvchilar</b>")
        await callback.message.edit_text(f"{terminal_header('growth report')}\n\nDavr: 30 kun\nKunlar: {len(rows)}", reply_markup=keyboards.back_home("adm:analytics"))


@router.callback_query(F.data == "analytics:support")
async def support_report(callback: CallbackQuery, analytics_service: AnalyticsService) -> None:
    if not await admin_callback_guard(callback): return
    await callback.answer()
    data = await analytics_service.support_metrics()
    avg = data.get("avg_first_reply_minutes")
    text = (f"{terminal_header('support analytics')}\n\nJami murojaatlar: <b>{data['total']}</b>\n"
            f"Ochiq: <b>{data['opened']}</b>\nYopilgan: <b>{data['closed']}</b>\n"
            f"O‘rtacha birinchi javob: <b>{avg if avg is not None else 'Ma’lumot yo‘q'} daqiqa</b>")
    if callback.message: await callback.message.edit_text(text, reply_markup=keyboards.back_home("adm:analytics"))


@router.callback_query(F.data == "analytics:ai")
async def ai_analyst(callback: CallbackQuery, analytics_service: AnalyticsService, ai_service: AIService) -> None:
    if not await admin_callback_guard(callback): return
    await callback.answer()
    stats = await analytics_service.dashboard()
    support = await analytics_service.support_metrics()
    payload = {"dashboard": stats, "support_30d": support}
    if callback.message:
        msg = await callback.message.answer("🧠 AI tahlilchi statistikani o‘rganmoqda...")
        try:
            result = await ai_service.generate(
                callback.from_user.id, "analytics_analyst",
                "Siz analitik yordamchisiz. Faqat berilgan JSON ma'lumotlarga tayaning. O'zbek lotinida 5 ta xulosa va 3 ta aniq amaliy tavsiya bering. Yetishmagan metrikalarni uydirmang.",
                json.dumps(payload, ensure_ascii=False), max_tokens=1400,
            )
            await msg.edit_text(f"{terminal_header('ai analyst')}\n\n{html.escape(result.text)[:3800]}", reply_markup=keyboards.back_home("adm:analytics"))
        except Exception as exc:
            await msg.edit_text(f"AI tahlili bajarilmadi: {html.escape(str(exc)[:300])}", reply_markup=keyboards.back_home("adm:analytics"))
