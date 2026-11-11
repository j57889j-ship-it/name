"""All Telegram buttons are real InlineKeyboardButton objects, never HTML."""
from __future__ import annotations
from aiogram.types import InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder


def _kb(rows: list[list[tuple[str, str]]]) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    for row in rows:
        builder.row(*[__button(text, data) for text, data in row])
    return builder.as_markup()


def __button(text: str, data: str):
    from aiogram.types import InlineKeyboardButton
    return InlineKeyboardButton(text=text, callback_data=data)


def subscription(channel_url: str) -> InlineKeyboardMarkup:
    from aiogram.types import InlineKeyboardButton
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📢 Kanalga obuna bo‘lish", url=channel_url)],
        [InlineKeyboardButton(text="✅ Tekshirish", callback_data="sub:check")],
    ])


def user_home() -> InlineKeyboardMarkup:
    return _kb([[ ("💬 Adminga murojaat", "user:contact") ]])


def admin_home() -> InlineKeyboardMarkup:
    return _kb([
        [("🧠 AI Prompt Studio", "adm:ai"), ("✍️ Content Studio", "adm:posts")],
        [("📢 Kanal boshqaruvi", "adm:channel"), ("🕒 Scheduler", "adm:schedule")],
        [("💬 Murojaatlar", "adm:tickets"), ("📊 Analytics", "adm:analytics")],
        [("🛰 AI Research", "adm:research"), ("👥 Foydalanuvchilar", "adm:users")],
        [("📣 Broadcast", "adm:broadcast"), ("💾 Backup & Tools", "adm:tools")],
        [("⚙️ Sozlamalar", "adm:settings"), ("🛡 Security", "adm:security")],
    ])


def back_home(back: str = "adm:home") -> InlineKeyboardMarkup:
    return _kb([[ ("⬅️ Orqaga", back), ("🏠 Bosh menyu", "adm:home") ]])


def categories() -> InlineKeyboardMarkup:
    return _kb([
        [("💻 Kod", "ai:cat:code"), ("✍️ Matn", "ai:cat:text")],
        [("🎨 Rasm", "ai:cat:image"), ("📊 Biznes", "ai:cat:business")],
        [("🎓 O‘qish", "ai:cat:study"), ("🧩 Boshqa", "ai:cat:other")],
        [("🏠 Menyu", "adm:home")],
    ])


def prompt_actions(prompt_id: int | None = None) -> InlineKeyboardMarkup:
    rows = [
        [("🔄 Qayta yaratish", "ai:again"), ("📈 Kuchaytirish", "ai:improve")],
        [("✂️ Qisqartirish", "ai:shorten"), ("🌐 Inglizcha", "ai:english")],
    ]
    rows.append([("💾 Kutubxonaga saqlash", "ai:save"), ("📚 Kutubxona", "ai:library")])
    rows.append([("📢 Kanalga joylash", "ai:publish")])
    rows.append([("🏠 Menyu", "adm:home")])
    return _kb(rows)


def post_variants() -> InlineKeyboardMarkup:
    return _kb([
        [("1-variant", "post:variant:0"), ("2-variant", "post:variant:1"), ("3-variant", "post:variant:2")],
        [("🔄 Qayta yozish", "post:rewrite"), ("🏠 Menyu", "adm:home")],
    ])


def post_preview() -> InlineKeyboardMarkup:
    return _kb([
        [("✅ Hozir joylash", "post:publish"), ("🕒 Rejalashtirish", "post:schedule")],
        [("🎨 Terminal", "post:style:terminal"), ("🗂 Card", "post:style:card"), ("▫️ Minimal", "post:style:minimal"), ("✒️ Script", "post:style:script")],
        [("𝐁 Bold", "post:font:bold"), ("𝗦 Sans", "post:font:sans"), ("𝙼 Mono", "post:font:mono"), ("𝓢 Script", "post:font:script")],
        [("✏️ Tahrirlash", "post:edit"), ("🔁 Qayta yozish", "post:rewrite")],
        [("🗑 Bekor qilish", "post:cancel"), ("🏠 Menyu", "adm:home")],
    ])


def ticket_actions(ticket_id: int) -> InlineKeyboardMarkup:
    return _kb([
        [("↩️ Javob berish", f"ticket:reply:{ticket_id}"), ("🏷 Teg", f"ticket:tag:{ticket_id}")],
        [("⏳ Jarayonda", f"ticket:progress:{ticket_id}"), ("✅ Yopish", f"ticket:close:{ticket_id}")],
        [("⭐ Muhim", f"ticket:star:{ticket_id}"), ("🚫 Ban", f"ticket:ban:{ticket_id}")],
    ])


def settings_menu(values: dict[str, str]) -> InlineKeyboardMarkup:
    sub = "ON" if values.get("subscription_required", "true") == "true" else "OFF"
    effects = "ON" if values.get("effects_enabled", "true") == "true" else "OFF"
    react = "ON" if values.get("auto_reaction_enabled", "true") == "true" else "OFF"
    return _kb([
        [(f"🔐 Obuna: {sub}", "set:toggle:subscription_required"), (f"✨ Effekt: {effects}", "set:toggle:effects_enabled")],
        [(f"🔥 Reaksiya: {react}", "set:toggle:auto_reaction_enabled"), ("😀 Emoji tanlash", "set:emoji")],
        [("🔔 Ticket xabari", "set:toggle:notify_new_ticket"), ("🧠 AI limit", "set:ai_limit")],
        [("🎨 Post uslubi", "set:style"), ("🔤 Sarlavha shrift", "set:font")],
        [("📑 Haftalik hisobot", "set:toggle:weekly_report_enabled"), ("🧠 AI provayder", "set:provider")],
        [("🏠 Menyu", "adm:home")],
    ])


def simple_choices(prefix: str, options: list[tuple[str, str]]) -> InlineKeyboardMarkup:
    rows = [[(title, f"{prefix}:{value}")] for title, value in options]
    rows.append([("⬅️ Orqaga", "adm:settings"), ("🏠 Menyu", "adm:home")])
    return _kb(rows)
