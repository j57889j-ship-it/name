"""Admin home and module landing pages."""
from aiogram import Router, F
from aiogram.filters import Command
from aiogram.types import Message, CallbackQuery
from bot.middlewares.admin_only import AdminFilter
from bot.handlers.common import admin_callback_guard
from bot.ui import keyboards, texts
from bot.ui.theme import terminal_header
from bot.security import is_admin
from bot.config import settings

router = Router(name="admin-panel")
router.message.filter(AdminFilter())
router.callback_query.filter(AdminFilter())


async def render_admin_home(repo) -> str:
    """Build a live, database-backed admin status card."""
    stats = await repo.fetchrow("""SELECT
        (SELECT COUNT(*) FROM users WHERE is_banned=FALSE) AS users,
        (SELECT COUNT(*) FROM tickets WHERE status<>'closed') AS tickets,
        (SELECT COUNT(*) FROM scheduled_jobs WHERE active=TRUE) AS scheduled,
        (SELECT COUNT(*) FROM users WHERE joined_at::date=CURRENT_DATE) AS new_today""")
    provider = await repo.get_setting("ai_provider", settings.ai_provider)
    return (texts.ADMIN_HOME + "\n\n"
            f"👥 Foydalanuvchilar: <b>{stats['users']}</b>  ·  🆕 Bugun: <b>{stats['new_today']}</b>\n"
            f"💬 Ochiq ticketlar: <b>{stats['tickets']}</b>  ·  🕒 Rejalar: <b>{stats['scheduled']}</b>\n"
            f"🧠 AI: <b>{provider.upper()}</b>  ·  🛰 Webhook: <b>ACTIVE</b>")


@router.message(Command("admin"))
async def admin_command(message: Message, state, repo) -> None:
    if not is_admin(message.from_user.id):
        await message.answer(texts.NOT_FOUND)
        return
    await state.clear()
    await repo.audit(message.from_user.id, "open_admin_panel")
    await message.answer(await render_admin_home(repo), reply_markup=keyboards.admin_home())


@router.callback_query(F.data == "adm:home")
async def admin_home_callback(callback: CallbackQuery, state, repo) -> None:
    if not await admin_callback_guard(callback): return
    await callback.answer()
    await state.clear()
    if callback.message:
        await callback.message.edit_text(await render_admin_home(repo), reply_markup=keyboards.admin_home())


@router.callback_query(F.data == "adm:channel")
async def channel_menu(callback: CallbackQuery) -> None:
    if not await admin_callback_guard(callback): return
    await callback.answer()
    if callback.message:
        await callback.message.edit_text(
            f"{terminal_header('channel control')}\n\n📢 <b>Kanal boshqaruvi</b>\nPost nashri, pin, reaksiyalar va postlar tarixi.",
            reply_markup=keyboards._kb([
                [("✍️ Yangi post", "adm:posts"), ("🔥 Reaksiya sozlamasi", "adm:settings")],
                [("📚 Nashrlar tarixi", "adm:schedule"), ("📊 Kontent tahlili", "adm:analytics")],
                [("🏠 Bosh menyu", "adm:home")],
            ]),
        )
