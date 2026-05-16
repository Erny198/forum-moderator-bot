from __future__ import annotations

import logging
from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_session
from app.models import User

logger = logging.getLogger(__name__)


async def get_or_create_user(
    telegram_id: int,
    username: Optional[str] = None,
    first_name: Optional[str] = None,
    last_name: Optional[str] = None,
) -> User:
    """Get existing user or create new one."""
    async with get_session() as session:
        result = await session.execute(
            select(User).where(User.telegram_id == telegram_id)
        )
        user = result.scalar_one_or_none()

        if user is None:
            user = User(
                telegram_id=telegram_id,
                username=username,
                first_name=first_name,
                last_name=last_name,
                role="participant",
            )
            session.add(user)
            await session.flush()
            await session.refresh(user)
            logger.info("Created new user: telegram_id=%d username=%s", telegram_id, username)
        else:
            # Update fields if changed
            updated = False
            if username is not None and user.username != username:
                user.username = username
                updated = True
            if first_name is not None and user.first_name != first_name:
                user.first_name = first_name
                updated = True
            if last_name is not None and user.last_name != last_name:
                user.last_name = last_name
                updated = True
            if updated:
                await session.flush()

        return user


async def get_user_by_telegram_id(telegram_id: int) -> Optional[User]:
    async with get_session() as session:
        result = await session.execute(
            select(User).where(User.telegram_id == telegram_id)
        )
        return result.scalar_one_or_none()


async def get_all_users_with_active_commitments() -> list[User]:
    """Return users who have at least one active commitment."""
    from app.models import Commitment
    async with get_session() as session:
        result = await session.execute(
            select(User)
            .join(Commitment, Commitment.telegram_user_id == User.telegram_id)
            .where(Commitment.status == "active")
            .distinct()
        )
        return list(result.scalars().all())
