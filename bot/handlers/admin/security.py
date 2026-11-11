"""Security center and emergency publishing/broadcast pause."""
from aiogram import Router, F
from aiogram.types import CallbackQuery
from bot.middlewares.admin_only import AdminFilter
from bot.handlers.common import admin_callback_guard
from bot.ui import keyboards
from bot.ui.theme import terminal_header

router = Router(name="admin-security")
router.callback_query.filter(AdminFilter())


@router.callback_query(F.data == "adm:security")
async def security_center(callback: CallbackQuery, repo) -> None:
    if not await admin_callback_guard(callback): return
    await callback.answer()
    publish_paused = await repo.get_setting("publishing_paused", "false") == "true"
    broadcast_paused = await repo.get_setting("broadcast_paused", "false") == "true"
    from aiogram.utils.keyboard import InlineKeyboardBuilder
    builder = InlineKeyboardBuilder()
    builder.button(text=f"{'▶️' if publish_paused else '⛔'} Publishing {'PAUSED' if publish_paused else 'ACTIVE'}", callback_data="security:toggle:publishing_paused")
    builder.button(text=f"{'▶️' if broadcast_paused else '⛔'} Broadcast {'PAUSED' if broadcast_paused else 'ACTIVE'}", callback_data="security:toggle:broadcast_paused")
    builder.button(text="🧾 Admin ID ro‘yxati", callback_data="security:admins")
    builder.adjust(1)
    builder.row(keyboards.__button("🏠 Bosh menyu", "adm:home"))
    if callback.message:
        await callback.message.edit_text(f"{terminal_header('security center')}\n\n🛡 <b>Favqulodda boshqaruv</b>\nPublishing va broadcast jarayonlarini alohida to‘xtatish mumkin.\n\nOwner ID'lar: <code>{len(__import__('bot.config', fromlist=['settings']).settings.admin_ids)}</code>", reply_markup=builder.as_markup())


@router.callback_query(F.data.startswith("security:toggle:"))
async def security_toggle(callback: CallbackQuery, repo) -> None:
    if not await admin_callback_guard(callback): return
    key = (callback.data or "").split(":")[-1]
    if key not in {"publishing_paused", "broadcast_paused"}:
        await callback.answer("Noma’lum amal.", show_alert=True); return
    old = await repo.get_setting(key, "false")
    new = "false" if old == "true" else "true"
    await repo.set_setting(key, new)
    await repo.audit(callback.from_user.id, "emergency_switch", {"key": key, "value": new})
    await callback.answer("To‘xtatildi." if new == "true" else "Qayta faollashtirildi.", show_alert=True)
    await security_center(callback, repo)


@router.callback_query(F.data == "security:admins")
async def security_admins(callback: CallbackQuery) -> None:
    if not await admin_callback_guard(callback): return
    from bot.config import settings
    await callback.answer()
    text = f"{terminal_header('authorized admins')}\n\n" + "\n".join(f"<code>{admin_id}</code>" for admin_id in sorted(settings.admin_ids))
    if callback.message: await callback.message.edit_text(text, reply_markup=keyboards.back_home("adm:security"))
