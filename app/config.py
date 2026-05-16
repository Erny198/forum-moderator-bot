from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import Optional

from dotenv import load_dotenv

load_dotenv()


def _require(name: str) -> str:
    value = os.getenv(name)
    if not value:
        raise ValueError(f"Required environment variable '{name}' is not set.")
    return value


def _optional(name: str, default: str = "") -> str:
    return os.getenv(name, default)


@dataclass
class Config:
    bot_token: str
    database_url: str
    group_chat_id: int
    moderator_telegram_id: int

    openai_api_key: str = ""
    openai_model: str = "gpt-4.1-mini"
    anthropic_api_key: str = ""
    anthropic_model: str = "claude-haiku-4-5-20251001"
    ai_provider: str = "anthropic"

    timezone: str = "Europe/Moscow"
    weekly_reminder_day: str = "MONDAY"
    weekly_reminder_time: str = "10:00"

    log_level: str = "INFO"

    @classmethod
    def from_env(cls) -> "Config":
        bot_token = _require("BOT_TOKEN")
        database_url = _require("DATABASE_URL")
        group_chat_id_str = _require("GROUP_CHAT_ID")
        moderator_id_str = _require("MODERATOR_TELEGRAM_ID")

        try:
            group_chat_id = int(group_chat_id_str)
        except ValueError:
            raise ValueError("GROUP_CHAT_ID must be an integer.")

        try:
            moderator_telegram_id = int(moderator_id_str)
        except ValueError:
            raise ValueError("MODERATOR_TELEGRAM_ID must be an integer.")

        ai_provider = _optional("AI_PROVIDER", "anthropic").lower()

        openai_api_key = _optional("OPENAI_API_KEY", "")
        anthropic_api_key = _optional("ANTHROPIC_API_KEY", "")

        if ai_provider == "openai" and not openai_api_key:
            raise ValueError("OPENAI_API_KEY is required when AI_PROVIDER=openai.")
        if ai_provider == "anthropic" and not anthropic_api_key:
            raise ValueError("ANTHROPIC_API_KEY is required when AI_PROVIDER=anthropic.")

        return cls(
            bot_token=bot_token,
            database_url=database_url,
            group_chat_id=group_chat_id,
            moderator_telegram_id=moderator_telegram_id,
            openai_api_key=openai_api_key,
            openai_model=_optional("OPENAI_MODEL", "gpt-4.1-mini"),
            anthropic_api_key=anthropic_api_key,
            anthropic_model=_optional("ANTHROPIC_MODEL", "claude-haiku-4-5-20251001"),
            ai_provider=ai_provider,
            timezone=_optional("TIMEZONE", "Europe/Moscow"),
            weekly_reminder_day=_optional("WEEKLY_REMINDER_DAY", "MONDAY").upper(),
            weekly_reminder_time=_optional("WEEKLY_REMINDER_TIME", "10:00"),
            log_level=_optional("LOG_LEVEL", "INFO").upper(),
        )


config: Config = Config.from_env()
