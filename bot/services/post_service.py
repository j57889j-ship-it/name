"""Telegram post validation, publishing, and reaction handling."""
from __future__ import annotations
import re
import bleach
from aiogram import Bot
from aiogram.enums import ParseMode
from aiogram.types import ReactionTypeEmoji
from aiogram.exceptions import TelegramAPIError
from bot.config import settings
from bot.ui.stylizer import render_post

ALLOWED_TAGS = {"b", "strong", "i", "em", "u", "ins", "s", "strike", "del", "code", "pre", "blockquote", "a", "tg-spoiler"}
ALLOWED_ATTRIBUTES = {"a": ["href"]}


def clean_telegram_html(value: str) -> str:
    """Sanitize generated HTML to Telegram's narrow formatting allowlist."""
    cleaned = bleach.clean(
        value, tags=ALLOWED_TAGS, attributes=ALLOWED_ATTRIBUTES,
        protocols={"http", "https", "tg"}, strip=True,
    )
    cleaned = re.sub(r"<pre>\s*<code>(.*?)</code>\s*</pre>", r"<pre>\1</pre>", cleaned, flags=re.S)
    return cleaned.strip()


def telegram_length(value: str) -> int:
    """Return a conservative plain-text length estimate for Telegram limits."""
    return len(re.sub(r"<[^>]+>", "", bleach.clean(value, tags=set(), strip=True)))


class PostService:
    def __init__(self, bot: Bot, repo) -> None:
        self.bot = bot
        self.repo = repo

    async def publish(self, post_id: int) -> int:
        if await self.repo.get_setting("publishing_paused", "false") == "true":
            raise RuntimeError("Favqulodda xavfsizlik rejimi: kanalga nashr vaqtincha to‘xtatilgan.")
        post = await self.repo.get_post(post_id)
        if not post:
            raise ValueError("Post topilmadi")
        body = clean_telegram_html(render_post(post["body_html"], post["style"], post["font"]))
        if not body:
            raise ValueError("Post matni bo‘sh")
        if len(body) > 4096:
            raise ValueError("Post 4096 belgilik Telegram chegarasidan oshdi")
        media_type = post["media_type"]
        media_file_id = post["media_file_id"]
        if media_type and media_file_id:
            if telegram_length(body) > 1024:
                raise ValueError("Rasm/video captioni 1024 belgidan oshmasligi kerak. Postni qisqartiring.")
            sender = {
                "photo": self.bot.send_photo,
                "video": self.bot.send_video,
                "document": self.bot.send_document,
                "animation": self.bot.send_animation,
                "audio": self.bot.send_audio,
                "voice": self.bot.send_voice,
            }.get(media_type)
            if sender is None:
                raise ValueError("Bu media turi kanal posti sifatida qo‘llab-quvvatlanmaydi.")
            message = await sender(
                chat_id=settings.channel_id, **{media_type: media_file_id},
                caption=body, parse_mode=ParseMode.HTML,
            )
        else:
            message = await self.bot.send_message(
                chat_id=settings.channel_id, text=body, parse_mode=ParseMode.HTML,
                disable_web_page_preview=False,
            )
        await self.repo.execute(
            "UPDATE posts SET status='published',channel_message_id=$1,published_at=NOW() WHERE id=$2",
            message.message_id, post_id,
        )
        await self.repo.log_event("post_published", None, {"post_id": post_id, "message_id": message.message_id})
        enabled = await self.repo.get_setting("auto_reaction_enabled", "true") == "true"
        emoji = await self.repo.get_setting("auto_reaction_emoji", settings.auto_reaction_emoji)
        if enabled:
            try:
                await self.bot.set_message_reaction(
                    chat_id=settings.channel_id, message_id=message.message_id,
                    reaction=[ReactionTypeEmoji(emoji=emoji)],
                )
            except TelegramAPIError:
                await self.repo.log_event("reaction_failed", None, {"post_id": post_id, "emoji": emoji})
        return message.message_id

    async def record_reaction_counts(self, message_id: int, reactions: list[dict]) -> None:
        post = await self.repo.fetchrow("SELECT id FROM posts WHERE channel_message_id=$1", message_id)
        if not post:
            return
        import json
        counts = {}
        for item in reactions:
            reaction = item.get("type", {})
            emoji = reaction.get("emoji") or reaction.get("custom_emoji_id") or "unknown"
            counts[emoji] = item.get("total_count", 0)
        await self.repo.execute(
            "INSERT INTO post_reaction_snapshots(post_id,emoji_counts) VALUES($1,$2::jsonb)",
            post["id"], json.dumps(counts, ensure_ascii=False),
        )
