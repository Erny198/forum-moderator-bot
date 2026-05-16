from __future__ import annotations

import logging
from datetime import datetime
from typing import Optional

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert

from app.database import get_session
from app.models import ForumSettings

logger = logging.getLogger(__name__)


async def get_forum_settings(group_chat_id: int) -> Optional[ForumSettings]:
    async with get_session() as session:
        result = await session.execute(
            select(ForumSettings).where(ForumSettings.group_chat_id == group_chat_id)
        )
        return result.scalar_one_or_none()


async def set_next_forum_date(group_chat_id: int, next_forum_at: datetime) -> ForumSettings:
    async with get_session() as session:
        result = await session.execute(
            select(ForumSettings).where(ForumSettings.group_chat_id == group_chat_id)
        )
        settings = result.scalar_one_or_none()

        if settings is None:
            settings = ForumSettings(
                group_chat_id=group_chat_id,
                next_forum_at=next_forum_at,
            )
            session.add(settings)
        else:
            settings.next_forum_at = next_forum_at

        await session.flush()
        await session.refresh(settings)
        logger.info(
            "Forum date set for chat=%d: %s", group_chat_id, next_forum_at
        )
        return settings
