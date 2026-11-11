"""Live database-backed admin settings."""
from aiogram import Router, F
from aiogram.types import CallbackQuery, Message
from aiogram.fsm.context import FSMContext
from bot.middlewares.admin_only import AdminFilter
from bot.handlers.common import admin_callback_guard
from bot.ui import keyboards
from bot.ui.theme import terminal_header
from bot.states import AdminStates
from bot.config import settings
from zoneinfo import ZoneInfo
from apscheduler.triggers.cron import CronTrigger

router = Router(name="admin-settings")
router.callback_query.filter(AdminFilter())
router.message.filter(AdminFilter())
TOGGLES = {"subscription_required", "effects_enabled", "auto_reaction_enabled", "notify_new_ticket", "weekly_report_enabled"}


@router.callback_query(F.data == "adm:settings")
async def settings_menu(callback: CallbackQuery, repo) -> None:
    if not await admin_callback_guard(callback): return
    await callback.answer()
    keys = ["subscription_required", "effects_enabled", "auto_reaction_enabled", "auto_reaction_emoji", "notify_new_ticket", "weekly_report_enabled"]
    values = {key: await repo.get_setting(key, "") for key in keys}
    if callback.message:
        await callback.message.edit_text(f"{terminal_header('system settings')}\n\n⚙️ <b>Bot sozlamalari</b>\nO‘zgarishlar restart talab qilmaydi.", reply_markup=keyboards.settings_menu(values))


@router.callback_query(F.data.startswith("set:toggle:"))
async def toggle_setting(callback: CallbackQuery, repo, scheduler_service) -> None:
    if not await admin_callback_guard(callback): return
    key = (callback.data or "").split(":")[-1]
    if key not in TOGGLES:
        await callback.answer("Noma’lum sozlama.", show_alert=True)
        return
    old = await repo.get_setting(key, "false")
    new = "false" if old == "true" else "true"
    await repo.set_setting(key, new)
    await repo.audit(callback.from_user.id, "setting_changed", {"key": key, "value": new})
    if key == "weekly_report_enabled":
        try:
            if new == "true" and hasattr(scheduler_service, "weekly_report_job"):
                scheduler_service.scheduler.add_job(scheduler_service.weekly_report_job, CronTrigger(day_of_week="sun", hour=20, minute=0, timezone=ZoneInfo(settings.timezone)), id="weekly-report", replace_existing=True)
            elif new == "false":
                scheduler_service.scheduler.remove_job("weekly-report")
        except Exception:
            pass
    await callback.answer(f"{key}: {new}")
    keys = ["subscription_required", "effects_enabled", "auto_reaction_enabled", "auto_reaction_emoji", "notify_new_ticket", "weekly_report_enabled"]
    values = {item: await repo.get_setting(item, "") for item in keys}
    if callback.message: await callback.message.edit_reply_markup(reply_markup=keyboards.settings_menu(values))


@router.callback_query(F.data == "set:emoji")
async def choose_emoji(callback: CallbackQuery) -> None:
    if not await admin_callback_guard(callback): return
    await callback.answer()
    if callback.message:
        await callback.message.edit_text("Reaksiya emojisini tanlang:", reply_markup=keyboards.simple_choices("set:emoji", [(e, e) for e in ["🔥", "🤯", "👨‍💻", "👾", "💯", "⚡"]]))


@router.callback_query(F.data.startswith("set:emoji:"))
async def save_emoji(callback: CallbackQuery, repo) -> None:
    if not await admin_callback_guard(callback): return
    emoji = (callback.data or "").split(":", 2)[-1]
    if emoji not in {"🔥", "🤯", "👨‍💻", "👾", "💯", "⚡"}:
        await callback.answer("Emoji ruxsat etilmagan.", show_alert=True)
        return
    await repo.set_setting("auto_reaction_emoji", emoji)
    await repo.audit(callback.from_user.id, "reaction_emoji_changed", {"emoji": emoji})
    await callback.answer(f"Reaksiya: {emoji}")
    if callback.message: await callback.message.edit_text(f"🟢 Standart reaksiya {emoji} qilib saqlandi.", reply_markup=keyboards.back_home("adm:settings"))


@router.callback_query(F.data == "set:ai_limit")
async def ai_limit_start(callback: CallbackQuery, state: FSMContext) -> None:
    if not await admin_callback_guard(callback): return
    await callback.answer()
    await state.set_state(AdminStates.waiting_ai_limit)
    if callback.message: await callback.message.answer("Kunlik AI so‘rovlari limitini son bilan yuboring (1–5000):")


@router.message(AdminStates.waiting_ai_limit)
async def ai_limit_input(message: Message, state: FSMContext, repo) -> None:
    try: limit = int((message.text or "").strip())
    except ValueError: limit = 0
    if not 1 <= limit <= 5000:
        await message.answer("⚠️ 1 dan 5000 gacha butun son yuboring.")
        return
    await repo.set_setting("ai_daily_limit", str(limit))
    await repo.audit(message.from_user.id, "ai_limit_changed", {"limit": limit})
    await state.clear()
    await message.answer(f"🟢 Kunlik AI limiti {limit} qilib saqlandi.", reply_markup=keyboards.back_home("adm:settings"))


@router.callback_query(F.data == "set:provider")
async def provider_menu(callback: CallbackQuery) -> None:
    if not await admin_callback_guard(callback): return
    from aiogram.utils.keyboard import InlineKeyboardBuilder
    builder = InlineKeyboardBuilder()
    if settings.openai_api_key:
        builder.button(text="OpenAI", callback_data="set:provider:openai")
    if settings.anthropic_api_key:
        builder.button(text="Anthropic", callback_data="set:provider:anthropic")
    builder.adjust(1)
    builder.row(keyboards.__button("⬅️ Sozlamalar", "adm:settings"))
    await callback.answer()
    if callback.message: await callback.message.edit_text("AI provayderini tanlang:", reply_markup=builder.as_markup())


@router.callback_query(F.data.startswith("set:provider:"))
async def provider_save(callback: CallbackQuery, repo) -> None:
    if not await admin_callback_guard(callback): return
    provider = (callback.data or "").split(":")[-1]
    available = {"openai": bool(settings.openai_api_key), "anthropic": bool(settings.anthropic_api_key)}
    if provider not in available or not available[provider]:
        await callback.answer("Bu provider API kaliti sozlanmagan.", show_alert=True); return
    await repo.set_setting("ai_provider", provider)
    await repo.audit(callback.from_user.id, "ai_provider_changed", {"provider": provider})
    await callback.answer(f"AI provayder: {provider}")
    if callback.message: await callback.message.edit_text(f"🟢 AI provayder {provider} qilib saqlandi.", reply_markup=keyboards.back_home("adm:settings"))


@router.callback_query(F.data == "set:style")
async def choose_style(callback: CallbackQuery) -> None:
    if not await admin_callback_guard(callback): return
    await callback.answer()
    if callback.message:
        await callback.message.edit_text("Standart post uslubini tanlang:", reply_markup=keyboards.simple_choices("set:style", [("Terminal", "terminal"), ("Card", "card"), ("Minimal", "minimal"), ("Script", "script")]))


@router.callback_query(F.data.startswith("set:style:"))
async def save_style(callback: CallbackQuery, repo) -> None:
    if not await admin_callback_guard(callback): return
    style = (callback.data or "").split(":")[-1]
    if style not in {"terminal", "card", "minimal", "script"}:
        await callback.answer("Noma’lum uslub.", show_alert=True); return
    await repo.set_setting("default_post_style", style)
    await callback.answer("Uslub saqlandi.")
    if callback.message: await callback.message.edit_text(f"🎨 Standart uslub: {style}", reply_markup=keyboards.back_home("adm:settings"))


@router.callback_query(F.data == "set:font")
async def font_menu(callback: CallbackQuery) -> None:
    if not await admin_callback_guard(callback): return
    await callback.answer()
    if callback.message:
        await callback.message.edit_text("Standart sarlavha shriftini tanlang:", reply_markup=keyboards.simple_choices("set:font", [("Bold", "bold"), ("Sans", "sans"), ("Bold Italic", "bolditalic"), ("Script", "script"), ("Mono", "mono"), ("Small Caps", "smallcaps")]))


@router.callback_query(F.data.startswith("set:font:"))
async def save_font(callback: CallbackQuery, repo) -> None:
    if not await admin_callback_guard(callback): return
    font = (callback.data or "").split(":")[-1]
    if font not in {"bold", "sans", "bolditalic", "script", "mono", "smallcaps"}:
        await callback.answer("Shrift topilmadi.", show_alert=True); return
    await repo.set_setting("default_post_font", font)
    await repo.audit(callback.from_user.id, "default_font_changed", {"font": font})
    await callback.answer("Standart shrift saqlandi.")
    if callback.message: await callback.message.edit_text(f"🟢 Standart shrift: {font}", reply_markup=keyboards.back_home("adm:settings"))
