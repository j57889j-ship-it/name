"""Admin schedule list and post-job cancellation."""
import html
from aiogram import Router, F
from aiogram.types import CallbackQuery
from bot.middlewares.admin_only import AdminFilter
from bot.handlers.common import admin_callback_guard
from bot.ui import keyboards
from bot.ui.theme import terminal_header

router = Router(name="admin-scheduler")
router.callback_query.filter(AdminFilter())


@router.callback_query(F.data == "adm:schedule")
async def schedule_list(callback: CallbackQuery, repo) -> None:
    if not await admin_callback_guard(callback): return
    await callback.answer()
    rows = await repo.fetch("""SELECT j.id,j.post_id,j.run_at,j.recurrence,p.title FROM scheduled_jobs j
        JOIN posts p ON p.id=j.post_id WHERE j.active=TRUE ORDER BY j.run_at LIMIT 15""")
    text = f"{terminal_header('scheduler')}\n\n🕒 <b>Rejalashtirilgan postlar</b>\n"
    from aiogram.utils.keyboard import InlineKeyboardBuilder
    builder = InlineKeyboardBuilder()
    for row in rows:
        text += f"\n<code>#{row['id']}</code> {row['run_at']:%Y-%m-%d %H:%M} · {row['recurrence']} · {html.escape(str(row['title'])[:45])}"
        builder.button(text=f"🗑 #{row['id']}", callback_data=f"schedule:cancel:{row['id']}")
    if not rows: text += "\nFaol reja mavjud emas."
    builder.adjust(2)
    builder.row(keyboards.__button("✍️ Yangi post", "adm:posts"), keyboards.__button("🏠 Menyu", "adm:home"))
    if callback.message: await callback.message.edit_text(text, reply_markup=builder.as_markup())


@router.callback_query(F.data.startswith("schedule:cancel:"))
async def cancel_schedule(callback: CallbackQuery, repo, scheduler_service) -> None:
    if not await admin_callback_guard(callback): return
    await callback.answer("Reja bekor qilindi.")
    job_id = int((callback.data or "schedule:cancel:0").split(":")[-1])
    await repo.execute("UPDATE scheduled_jobs SET active=FALSE WHERE id=$1", job_id)
    try: scheduler_service.scheduler.remove_job(f"scheduled-post-{job_id}")
    except Exception: pass
    await repo.audit(callback.from_user.id, "schedule_cancelled", {"job_id": job_id})
    if callback.message: await callback.message.edit_text(f"🟡 Reja #{job_id} bekor qilindi.", reply_markup=keyboards.back_home("adm:schedule"))
