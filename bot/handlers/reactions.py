"""Channel membership and anonymous reaction-count update handlers."""
from __future__ import annotations
from aiogram import Router, F
from aiogram.types import ChatMemberUpdated, MessageReactionCountUpdated
from aiogram.enums import ChatMemberStatus
from bot.config import settings

router = Router(name="channel-events")


@router.chat_member(F.chat.id == settings.channel_id)
async def channel_member_event(event: ChatMemberUpdated, repo, runtime) -> None:
    user = event.new_chat_member.user
    old_status = event.old_chat_member.status
    new_status = event.new_chat_member.status
    joined = new_status in {ChatMemberStatus.MEMBER, ChatMemberStatus.ADMINISTRATOR, ChatMemberStatus.CREATOR} or (new_status == ChatMemberStatus.RESTRICTED and bool(getattr(event.new_chat_member, "is_member", False)))
    was_member = old_status in {ChatMemberStatus.MEMBER, ChatMemberStatus.ADMINISTRATOR, ChatMemberStatus.CREATOR} or (old_status == ChatMemberStatus.RESTRICTED and bool(getattr(event.old_chat_member, "is_member", False)))
    if joined and not was_member:
        await repo.upsert_user(user.id, user.username, user.first_name or "", "channel_join")
        await repo.log_event("channel_join", user.id, {"chat_id": event.chat.id})
    elif was_member and not joined:
        await repo.log_event("channel_leave", user.id, {"chat_id": event.chat.id})
    await runtime.delete(f"sub:{settings.channel_id}:{user.id}")


@router.message_reaction_count(F.chat.id == settings.channel_id)
async def reaction_count_event(event: MessageReactionCountUpdated, repo, post_service) -> None:
    reactions = []
    for item in event.reactions:
        reaction_type = item.type
        if hasattr(reaction_type, "emoji"):
            kind = {"emoji": reaction_type.emoji}
        else:
            kind = {"custom_emoji_id": getattr(reaction_type, "custom_emoji_id", "unknown")}
        reactions.append({"type": kind, "total_count": item.total_count})
    await post_service.record_reaction_counts(event.message_id, reactions)
