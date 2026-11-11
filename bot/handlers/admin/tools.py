"""Admin tools: backup, health checks, audit log."""
from aiogram import Router, F
from aiogram.types import CallbackQuery
from aiogram.exceptions import TelegramAPIError
from bot.middlewares.admin_only import AdminFilter
from bot.handlers.common import admin_callback_guard
from bot.ui import keyboards
from bot.ui.theme import terminal_header
from bot.services.backup_service import create_backup
from bot.config import settings

router = Router(name="admin-tools")
router.callback_query.filter(AdminFilter())


@router.callback_query(F.data == "adm:tools")
async def tools_menu(callback: CallbackQuery) -> None:
    if not await admin_callback_guard(callback): return
    await callback.answer()
    from aiogram.utils.keyboard import InlineKeyboardBuilder
    builder = InlineKeyboardBuilder()
    builder.button(text="💾 Backup yaratish", callback_data="tool:backup")
    builder.button(text="🩺 Health check", callback_data="tool:health")
    builder.button(text="📜 Audit log", callback_data="tool:audit")
    builder.button(text="🧠 AI sarfi", callback_data="tool:ai_usage")
    builder.adjust(1)
    builder.row(keyboards.__button("🏠 Bosh menyu", "adm:home"))
    if callback.message:
        await callback.message.edit_text(f"{terminal_header('tools')}\n\n🛠 <b>Tizim asboblari</b>", reply_markup=builder.as_markup())


@router.callback_query(F.data == "tool:backup")
async def backup_action(callback: CallbackQuery, repo) -> None:
    if not await admin_callback_guard(callback): return
    await callback.answer("Backup tayyorlanmoqda...")
    if not callback.message: return
    try:
        document = await create_backup(repo)
        await callback.message.answer_document(document, caption="💾 <b>PostgreSQL mantiqiy backup</b>")
        await repo.audit(callback.from_user.id, "backup_created")
        await callback.message.edit_text("🟢 Backup tayyor va admin chatga yuborildi.", reply_markup=keyboards.back_home("adm:tools"))
    except Exception as exc:
        await callback.message.edit_text(f"🔴 Backup xatosi: {str(exc)[:250]}", reply_markup=keyboards.back_home("adm:tools"))


@router.callback_query(F.data == "tool:health")
async def health_check(callback: CallbackQuery, repo, runtime, scheduler_service) -> None:
    if not await admin_callback_guard(callback): return
    await callback.answer()
    db_ok = await repo.fetchrow("SELECT 1 AS ok") is not None
    redis_ok = await runtime.ping()
    try:
        me = await callback.bot.get_me()
        member = await callback.bot.get_chat_member(settings.channel_id, me.id)
        channel_ok = member.status in {"administrator", "creator"} and (member.status == "creator" or bool(getattr(member, "can_post_messages", False)))
    except TelegramAPIError:
        channel_ok = False
    text = (
        f"{terminal_header('health check')}\n\n"
        f"{'🟢' if db_ok else '🔴'} PostgreSQL: {'OK' if db_ok else 'FAIL'}\n"
        f"{'🟢' if redis_ok else '🟡'} Redis: {'OK' if redis_ok else 'FALLBACK MODE'}\n"
        f"{'🟢' if channel_ok else '🔴'} Kanal post huquqi: {'OK' if channel_ok else 'TEKSHIRING'}\n"
        f"🟢 Scheduler: {'RUNNING' if scheduler_service.scheduler.running else 'STOPPED'}\n"
        f"🧩 Rejalar: {len(scheduler_service.scheduler.get_jobs())}"
    )
    if callback.message: await callback.message.edit_text(text, reply_markup=keyboards.back_home("adm:tools"))


@router.callback_query(F.data == "tool:audit")
async def audit_log(callback: CallbackQuery, repo) -> None:
    if not await admin_callback_guard(callback): return
    await callback.answer()
    rows = await repo.fetch("SELECT admin_id,action,details,created_at FROM audit_log ORDER BY id DESC LIMIT 15")
    text = f"{terminal_header('audit log')}\n\n"
    for row in rows:
        text += f"<code>{row['created_at']:%m-%d %H:%M}</code> · <b>{row['action']}</b> · <code>{row['admin_id']}</code>\n"
    if not rows: text += "Audit log bo‘sh."
    if callback.message: await callback.message.edit_text(text[:3900], reply_markup=keyboards.back_home("adm:tools"))


@router.callback_query(F.data == "tool:ai_usage")
async def ai_usage_report(callback: CallbackQuery, repo) -> None:
    if not await admin_callback_guard(callback): return
    await callback.answer()
    data = await repo.ai_usage_today()
    text = (f"{terminal_header('ai usage')}\n\nBugungi so‘rovlar: <b>{data['requests']}</b>\n"
            f"Input tokenlar: <b>{data['input_tokens']}</b>\nOutput tokenlar: <b>{data['output_tokens']}</b>\n"
            f"Taxminiy xarajat: <b>${float(data['cost']):.6f}</b>\n"
            "Eslatma: narxlar .env dagi model tariflari asosida taxmin qilinadi.")
    if callback.message: await callback.message.edit_text(text, reply_markup=keyboards.back_home("adm:tools"))
