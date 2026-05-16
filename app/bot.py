from __future__ import annotations

import logging

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.fsm.storage.memory import MemoryStorage

from app.config import config
from app.handlers import callbacks, group_messages, moderator_commands, user_commands

logger = logging.getLogger(__name__)


def create_bot() -> Bot:
    return Bot(
        token=config.bot_token,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML),
    )


def create_dispatcher() -> Dispatcher:
    storage = MemoryStorage()
    dp = Dispatcher(storage=storage)

    # Register routers in priority order
    dp.include_router(callbacks.router)
    dp.include_router(moderator_commands.router)
    dp.include_router(user_commands.router)
    dp.include_router(group_messages.router)

    return dp
