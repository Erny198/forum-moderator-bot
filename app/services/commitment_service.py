from __future__ import annotations

import logging
from typing import Optional

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_session
from app.models import Commitment

logger = logging.getLogger(__name__)


async def create_commitment(
    telegram_user_id: int,
    group_chat_id: int,
    commitment_text: str,
    original_message_id: Optional[int] = None,
    deadline_text: Optional[str] = None,
) -> Commitment:
    async with get_session() as session:
        commitment = Commitment(
            telegram_user_id=telegram_user_id,
            group_chat_id=group_chat_id,
            commitment_text=commitment_text,
            original_message_id=original_message_id,
            deadline_text=deadline_text,
            status="active",
        )
        session.add(commitment)
        await session.flush()
        await session.refresh(commitment)
        logger.info(
            "Created commitment id=%d for user=%d",
            commitment.id,
            telegram_user_id,
        )
        return commitment


async def get_commitment_by_id(commitment_id: int) -> Optional[Commitment]:
    async with get_session() as session:
        result = await session.execute(
            select(Commitment).where(Commitment.id == commitment_id)
        )
        return result.scalar_one_or_none()


async def get_active_commitments_for_user(telegram_user_id: int) -> list[Commitment]:
    async with get_session() as session:
        result = await session.execute(
            select(Commitment)
            .where(
                Commitment.telegram_user_id == telegram_user_id,
                Commitment.status == "active",
            )
            .order_by(Commitment.created_at.asc())
        )
        return list(result.scalars().all())


async def get_all_active_commitments() -> list[Commitment]:
    async with get_session() as session:
        result = await session.execute(
            select(Commitment)
            .where(Commitment.status == "active")
            .order_by(Commitment.telegram_user_id, Commitment.created_at.asc())
        )
        return list(result.scalars().all())


async def mark_commitment_done(commitment_id: int) -> bool:
    async with get_session() as session:
        result = await session.execute(
            select(Commitment).where(Commitment.id == commitment_id)
        )
        commitment = result.scalar_one_or_none()
        if commitment is None:
            return False
        commitment.status = "done"
        return True


async def mark_commitment_cancelled(commitment_id: int) -> bool:
    async with get_session() as session:
        result = await session.execute(
            select(Commitment).where(Commitment.id == commitment_id)
        )
        commitment = result.scalar_one_or_none()
        if commitment is None:
            return False
        commitment.status = "cancelled"
        return True


async def update_commitment_text(commitment_id: int, new_text: str) -> bool:
    async with get_session() as session:
        result = await session.execute(
            select(Commitment).where(Commitment.id == commitment_id)
        )
        commitment = result.scalar_one_or_none()
        if commitment is None:
            return False
        commitment.commitment_text = new_text
        return True


async def is_original_message_already_processed(
    original_message_id: int, group_chat_id: int
) -> bool:
    """Check if a message was already saved as commitment."""
    async with get_session() as session:
        result = await session.execute(
            select(Commitment).where(
                Commitment.original_message_id == original_message_id,
                Commitment.group_chat_id == group_chat_id,
                Commitment.status != "cancelled",
            )
        )
        return result.scalar_one_or_none() is not None
