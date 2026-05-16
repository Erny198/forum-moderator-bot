from __future__ import annotations

import logging
from datetime import datetime
from typing import Optional

import pytz
from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message

from app.config import config
from app.services.commitment_service import get_all_active_commitments
from app.services.forum_service import get_forum_settings, set_next_forum_date
from app.services.reminder_service import (
    send_forum_notebook_reminder,
    send_weekly_commitment_reminders,
)
from app.services.user_service import get_user_by_telegram_id
from app.utils.dates import format_datetime, get_timezone

logger = logging.getLogger(__name__)
router = Router(name="moderator_commands")


def is_moderator(telegram_id: int) -> bool:
    return telegram_id == config.moderator_telegram_id


@router.message(Command("set_forum_date"))
async def cmd_set_forum_date(message: Message) -> None:
    if not is_moderator(message.from_user.id):
        await message.answer("У тебя нет прав для этой команды.")
        return

    args = message.text.split(maxsplit=1)
    if len(args) < 2:
        await message.answer(
            "Использование: /set_forum_date YYYY-MM-DD HH:MM\n"
            "Пример: /set_forum_date 2025-06-15 18:00"
        )
        return

    date_str = args[1].strip()
    tz = get_timezone()

    # Try multiple formats
    formats = ["%Y-%m-%d %H:%M", "%Y-%m-%d"]
    parsed_dt: Optional[datetime] = None
    for fmt in formats:
        try:
            parsed_dt = datetime.strptime(date_str, fmt)
            break
        except ValueError:
            continue

    if parsed_dt is None:
        await message.answer(
            "Неверный формат даты. Используй: YYYY-MM-DD HH:MM\n"
            "Пример: /set_forum_date 2025-06-15 18:00"
        )
        return

    # Localize to configured timezone
    try:
        localized_dt = tz.localize(parsed_dt)
    except Exception as exc:
        logger.error("Failed to localize date: %s", exc)
        await message.answer("Ошибка при обработке даты.")
        return

    try:
        settings = await set_next_forum_date(
            group_chat_id=config.group_chat_id,
            next_forum_at=localized_dt,
        )
        await message.answer(
            f"✅ Дата следующего форума установлена: {format_datetime(settings.next_forum_at)}"
        )
    except Exception as exc:
        logger.error("Failed to set forum date: %s", exc)
        await message.answer("Произошла ошибка при сохранении даты форума.")


@router.message(Command("forum_date"))
async def cmd_forum_date(message: Message) -> None:
    if not is_moderator(message.from_user.id):
        await message.answer("У тебя нет прав для этой команды.")
        return

    try:
        settings = await get_forum_settings(config.group_chat_id)
    except Exception as exc:
        logger.error("Failed to get forum settings: %s", exc)
        await message.answer("Ошибка при получении настроек форума.")
        return

    if settings is None or settings.next_forum_at is None:
        await message.answer("Дата следующего форума не установлена.")
        return

    await message.answer(
        f"📅 Следующий форум: {format_datetime(settings.next_forum_at)}"
    )


@router.message(Command("all_promises"))
async def cmd_all_promises(message: Message) -> None:
    if not is_moderator(message.from_user.id):
        await message.answer("У тебя нет прав для этой команды.")
        return

    try:
        commitments = await get_all_active_commitments()
    except Exception as exc:
        logger.error("Failed to get all commitments: %s", exc)
        await message.answer("Ошибка при получении обещаний.")
        return

    if not commitments:
        await message.answer("Нет активных обещаний.")
        return

    # Group by user
    user_commitments: dict[int, list] = {}
    for c in commitments:
        user_commitments.setdefault(c.telegram_user_id, []).append(c)

    lines = [f"📋 Все активные обещания ({len(commitments)}):\n"]
    for user_id, user_coms in user_commitments.items():
        # Try to get user info
        try:
            user = await get_user_by_telegram_id(user_id)
            if user:
                name = user.display_name()
            else:
                name = f"user_{user_id}"
        except Exception:
            name = f"user_{user_id}"

        lines.append(f"\n👤 {name}:")
        for c in user_coms:
            deadline_part = f" (до: {c.deadline_text})" if c.deadline_text else ""
            lines.append(f"  • {c.commitment_text}{deadline_part}")

    # Telegram message limit: 4096 chars
    full_text = "\n".join(lines)
    if len(full_text) <= 4096:
        await message.answer(full_text)
    else:
        # Split into chunks
        chunk = ""
        for line in lines:
            if len(chunk) + len(line) + 1 > 4000:
                await message.answer(chunk)
                chunk = line + "\n"
            else:
                chunk += line + "\n"
        if chunk.strip():
            await message.answer(chunk)


@router.message(Command("weekly_reminder_now"))
async def cmd_weekly_reminder_now(message: Message) -> None:
    if not is_moderator(message.from_user.id):
        await message.answer("У тебя нет прав для этой команды.")
        return

    await message.answer("Запускаю еженедельные напоминания...")
    try:
        bot = message.bot
        await send_weekly_commitment_reminders(bot)
        await message.answer("✅ Еженедельные напоминания отправлены.")
    except Exception as exc:
        logger.error("Failed to send weekly reminders manually: %s", exc)
        await message.answer(f"Ошибка при отправке напоминаний: {exc}")


@router.message(Command("forum_reminder_now"))
async def cmd_forum_reminder_now(message: Message) -> None:
    if not is_moderator(message.from_user.id):
        await message.answer("У тебя нет прав для этой команды.")
        return

    await message.answer("Запускаю напоминания о форуме...")
    try:
        bot = message.bot
        await send_forum_notebook_reminder(bot)
        await message.answer("✅ Напоминания о форуме отправлены.")
    except Exception as exc:
        logger.error("Failed to send forum reminders manually: %s", exc)
        await message.answer(f"Ошибка при отправке напоминаний: {exc}")
