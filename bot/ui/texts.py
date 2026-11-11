"""All end-user and admin-facing Uzbek interface text."""
from .theme import BANNER, terminal_header

WELCOME = f"<pre>{BANNER}</pre>\n{terminal_header('welcome')}\n\n🛰 <b>Dasturlash & AI tizimiga xush kelibsiz.</b>\n\nDavom etish uchun quyidagi tugmadan foydalaning."
SUBSCRIBE = (
    f"<pre>{BANNER}</pre>\n{terminal_header('subscription required')}\n\n"
    "🔒 <b>Kanalga obuna bo‘lish talab qilinadi.</b>\n"
    "Kanalga a’zo bo‘ling va keyin tekshirish tugmasini bosing."
)
USER_HOME = f"{terminal_header('user terminal')}\n\n🟢 <b>Ulanish muvaffaqiyatli.</b>\nSiz adminga murojaat yuborishingiz mumkin."
USER_HELP = "ℹ️ <b>Foydalanish:</b> /start — boshlash, /help — yordam. Boshqa imkoniyatlar faqat admin uchun."
NOT_FOUND = "⛔ Buyruq topilmadi."
ADMIN_DENIED = NOT_FOUND
ADMIN_HOME = (
    f"<pre>{BANNER}</pre>\n{terminal_header('admin control center')}\n\n"
    "🟢 <b>ADMIN ACCESS GRANTED</b>\n"
    "<code>AI CORE  •  DATABASE  •  CHANNEL  •  SCHEDULER</code>\n\n"
    "Kerakli boshqaruv modulini tanlang."
)
ERROR_CARD = "<code>root@dasturlash:~$ system_error</code>\n🔴 <b>Amalni bajarib bo‘lmadi.</b> Xatolik jurnalga yozildi."
CANCELLED = "🟡 Amal bekor qilindi."
