"""Short, rate-limit-aware visual effects for the cyber-terminal UI."""
from __future__ import annotations

import asyncio
import html
import random
from collections.abc import Sequence

from aiogram.exceptions import TelegramBadRequest, TelegramRetryAfter
from aiogram.types import Message, InlineKeyboardMarkup

SPINNERS = ("⠋", "⠙", "⠹", "⠸", "⠼", "⠴", "⠦", "⠧", "⠇", "⠏")
GLITCH_CHARS = "▓▒░<>/\\01#@$%"
EDIT_INTERVAL = 1.02


async def safe_edit(message: Message, text: str, **kwargs) -> None:
    """Edit a message and safely handle common Telegram edit/rate-limit errors."""
    try:
        await message.edit_text(text, **kwargs)
    except TelegramRetryAfter as exc:
        await asyncio.sleep(min(float(exc.retry_after), 2.0))
    except TelegramBadRequest as exc:
        if "message is not modified" not in str(exc).lower():
            raise


async def boot_sequence(message: Message, enabled: bool = True) -> None:
    """Show a short boot sequence that stays below four seconds."""
    if not enabled:
        return
    frames = [
        "<code>root@dasturlash:~$ boot</code>\n🟢 [ OK ] UI modullari yuklandi...",
        "<code>root@dasturlash:~$ boot</code>\n🟢 [ OK ] AI core tekshirildi...\n🟣 [ OK ] Database ulandi...",
        "<code>root@dasturlash:~$ boot</code>\n🟢 [ OK ] Barcha modullar tayyor\n🔓 [ ACCESS GRANTED ]",
    ]
    for index, frame in enumerate(frames):
        await safe_edit(message, frame)
        if index != len(frames) - 1:
            await asyncio.sleep(EDIT_INTERVAL)


async def loading(message: Message, enabled: bool = True, label: str = "AI so‘rov bajarilmoqda") -> None:
    """Animate three loading frames while work is running."""
    if not enabled:
        await safe_edit(message, f"⏳ {html.escape(label)}...")
        return
    for index, spinner in enumerate(SPINNERS[:3]):
        progress = "▓" * (index + 1) + "░" * (3 - index)
        await safe_edit(message, f"<code>root@dasturlash:~$ processing</code>\n{spinner} {html.escape(label)}...\n<code>{progress}</code>")
        if index != 2:
            await asyncio.sleep(EDIT_INTERVAL)


async def typewriter_reveal(
    message: Message,
    text: str,
    enabled: bool = True,
    reply_markup: InlineKeyboardMarkup | None = None,
) -> None:
    """Reveal plain text inside a pre block in three chunks; HTML is escaped."""
    if not enabled:
        await safe_edit(message, f"<pre>{html.escape(text)}</pre>", reply_markup=reply_markup)
        return
    if not text:
        await safe_edit(message, "<pre></pre>", reply_markup=reply_markup)
        return
    size = len(text)
    cuts = [max(1, size // 3), max(2, (size * 2) // 3), size]
    previous = 0
    for index, cut in enumerate(cuts):
        cut = min(size, max(cut, previous + 1))
        markup = reply_markup if index == len(cuts) - 1 else None
        await safe_edit(message, f"<pre>{html.escape(text[:cut])}</pre>", reply_markup=markup)
        previous = cut
        if index != len(cuts) - 1:
            await asyncio.sleep(EDIT_INTERVAL)


async def glitch_title(message: Message, title: str, enabled: bool = True) -> None:
    """Show two restrained glitch frames, then the final clean terminal title."""
    clean = html.escape(title)
    if not enabled or len(title) < 4:
        await safe_edit(message, f"<b>{clean}</b>")
        return
    for _ in range(2):
        chars = list(title)
        for index in random.sample(range(len(chars)), k=min(2, len(chars))):
            if not chars[index].isspace():
                chars[index] = random.choice(GLITCH_CHARS)
        await safe_edit(message, f"<b>{html.escape(''.join(chars))}</b>")
        await asyncio.sleep(EDIT_INTERVAL)
    await safe_edit(message, f"<b>{clean}</b>")


async def success_stamp(message: Message, text: str, enabled: bool = True, reply_markup: InlineKeyboardMarkup | None = None) -> None:
    """Replace a progress message with a consistent success stamp."""
    prefix = "🟢 <b>[ DEPLOYED ✅ ]</b>" if enabled else "✅ <b>[ TAYYOR ]</b>"
    await safe_edit(message, f"{prefix}\n{html.escape(text)}", reply_markup=reply_markup)


async def failure_stamp(message: Message, text: str, enabled: bool = True, reply_markup: InlineKeyboardMarkup | None = None) -> None:
    """Replace a progress message with a consistent failure stamp."""
    prefix = "🔴 <b>[ ACCESS DENIED ⛔ ]</b>" if enabled else "⛔ <b>[ XATOLIK ]</b>"
    await safe_edit(message, f"{prefix}\n{html.escape(text)}", reply_markup=reply_markup)
