from __future__ import annotations

import logging
from typing import Any

from aiogram import F, Router
from aiogram.types import Message

from app.config import config
from app.keyboards.inline import commitment_proposal_keyboard
from app.services.ai_service import analyze_message
from app.services.commitment_service import is_original_message_already_processed
from app.services.user_service import get_or_create_user

logger = logging.getLogger(__name__)
router = Router(name="group_messages")

# In-memory store for pending commitments
# Key: f"{group_chat_id}:{message_id}"
# Value: dict with commitment data
pending_commitments: dict[str, dict[str, Any]] = {}


def get_pending_key(group_chat_id: int, message_id: int) -> str:
    return f"{group_chat_id}:{message_id}"


def store_pending(
    group_chat_id: int,
    message_id: int,
    telegram_user_id: int,
    commitment_text: str,
    deadline_text: str | None,
    bot_reply_message_id: int | None = None,
) -> None:
    key = get_pending_key(group_chat_id, message_id)
    pending_commitments[key] = {
        "group_chat_id": group_chat_id,
        "original_message_id": message_id,
        "telegram_user_id": telegram_user_id,
        "commitment_text": commitment_text,
        "deadline_text": deadline_text,
        "bot_reply_message_id": bot_reply_message_id,
    }


def get_pending(group_chat_id: int, message_id: int) -> dict[str, Any] | None:
    key = get_pending_key(group_chat_id, message_id)
    return pending_commitments.get(key)


def remove_pending(group_chat_id: int, message_id: int) -> None:
    key = get_pending_key(group_chat_id, message_id)
    pending_commitments.pop(key, None)


@router.message(F.chat.id == config.group_chat_id)
async def handle_group_message(message: Message) -> None:
    # Skip messages from bots
    if message.from_user is None or message.from_user.is_bot:
        return

    # Only process text messages
    text = message.text or message.caption
    if not text:
        return

    # Auto-create/update user
    try:
        await get_or_create_user(
            telegram_id=message.from_user.id,
            username=message.from_user.username,
            first_name=message.from_user.first_name,
            last_name=message.from_user.last_name,
        )
    except Exception as exc:
        logger.error("Failed to upsert user %d: %s", message.from_user.id, exc)

    # Check deduplication: was this message already processed?
    try:
        already_done = await is_original_message_already_processed(
            original_message_id=message.message_id,
            group_chat_id=message.chat.id,
        )
        if already_done:
            return
    except Exception as exc:
        logger.error("Deduplication check failed: %s", exc)

    # Also check in-memory pending
    if get_pending(message.chat.id, message.message_id) is not None:
        return

    # Send to AI for analysis
    try:
        result = await analyze_message(text)
    except Exception as exc:
        logger.error("AI analysis error for message %d: %s", message.message_id, exc)
        return

    if result is None:
        return

    if not result.should_save:
        return

    commitment_text = result.commitment_text or text

    # Reply in group with proposal
    try:
        proposal_text = (
            f"Похоже, это обещание:\n\n"
            f"«{commitment_text}»\n\n"
            f"Зафиксировать?"
        )
        reply = await message.reply(
            text=proposal_text,
            reply_markup=commitment_proposal_keyboard(message.message_id),
        )
        store_pending(
            group_chat_id=message.chat.id,
            message_id=message.message_id,
            telegram_user_id=message.from_user.id,
            commitment_text=commitment_text,
            deadline_text=result.deadline_text,
            bot_reply_message_id=reply.message_id,
        )
        logger.info(
            "Proposed commitment for user=%d message=%d confidence=%.2f",
            message.from_user.id,
            message.message_id,
            result.confidence,
        )
    except Exception as exc:
        logger.error("Failed to send commitment proposal: %s", exc)
