from __future__ import annotations

import logging
from datetime import datetime
from typing import Optional

from sqlalchemy import select

from app.config import config
from app.database import get_session
from app.keyboards.inline import commitment_reminder_keyboard
from app.models import Commitment, ReminderLog, User
from app.services.commitment_service import get_all_active_commitments
from app.services.forum_service import get_forum_settings
from app.services.user_service import get_all_users_with_active_commitments
from app.utils.dates import is_tomorrow, now_in_tz

logger = logging.getLogger(__name__)

FORUM_NOTEBOOK_GROUP_MESSAGE = (
    "Завтра Форум.\n\n"
    "Пожалуйста, заполните тетрадь перед встречей:\n\n"
    "1. Что произошло с прошлого Форума?\n"
    "2. Какие обещания выполнены / не выполнены?\n"
    "3. Что сейчас занимает больше всего внимания?\n"
    "4. Какую тему хотите вынести в круг?\n"
    "5. Какой поддержки ждёте от группы?"
)

FORUM_NOTEBOOK_PRIVATE_MESSAGE = (
    "Завтра Форум.\n\nПожалуйста, не забудь заполнить тетрадь перед встречей."
)


async def _log_reminder(
    reminder_type: str,
    status: str,
    telegram_user_id: Optional[int] = None,
    commitment_id: Optional[int] = None,
    error_message: Optional[str] = None,
) -> None:
    try:
        async with get_session() as session:
            log = ReminderLog(
                telegram_user_id=telegram_user_id,
                commitment_id=commitment_id,
                reminder_type=reminder_type,
                sent_at=now_in_tz(),
                status=status,
                error_message=error_message,
            )
            session.add(log)
    except Exception as exc:
        logger.error("Failed to write reminder log: %s", exc)


async def send_weekly_commitment_reminders(bot) -> None:
    """Send weekly DM reminders to all users with active commitments."""
    logger.info("Starting weekly commitment reminders")
    all_commitments = await get_all_active_commitments()

    # Group by user
    user_commitments: dict[int, list[Commitment]] = {}
    for c in all_commitments:
        user_commitments.setdefault(c.telegram_user_id, []).append(c)

    if not user_commitments:
        logger.info("No active commitments found for weekly reminder")
        return

    for telegram_user_id, commitments in user_commitments.items():
        await _send_weekly_reminder_to_user(bot, telegram_user_id, commitments)


async def _send_weekly_reminder_to_user(bot, telegram_user_id: int, commitments: list[Commitment]) -> None:
    try:
        lines = ["Привет! Напоминаю о твоих активных обещаниях для Форум-группы:\n"]
        for idx, c in enumerate(commitments, start=1):
            lines.append(f"{idx}. {c.commitment_text}")
        lines.append("\nЧто уже выполнено?")
        text = "\n".join(lines)

        await bot.send_message(chat_id=telegram_user_id, text=text)

        # Send individual buttons for each commitment
        for c in commitments:
            await bot.send_message(
                chat_id=telegram_user_id,
                text=f"📌 {c.commitment_text}",
                reply_markup=commitment_reminder_keyboard(c.id),
            )

        await _log_reminder(
            reminder_type="weekly_commitments",
            status="sent",
            telegram_user_id=telegram_user_id,
        )
        logger.info("Sent weekly reminder to user=%d (%d commitments)", telegram_user_id, len(commitments))
    except Exception as exc:
        error_msg = str(exc)
        logger.error("Failed to send weekly reminder to user=%d: %s", telegram_user_id, error_msg)
        await _log_reminder(
            reminder_type="weekly_commitments",
            status="failed",
            telegram_user_id=telegram_user_id,
            error_message=error_msg,
        )
        # Notify moderator
        await _notify_moderator(bot, f"Не удалось отправить еженедельное напоминание пользователю {telegram_user_id}: {error_msg}")


async def send_forum_notebook_reminder(bot) -> None:
    """Send forum notebook reminder 1 day before the forum. Prevents duplicates."""
    forum_settings = await get_forum_settings(config.group_chat_id)
    if forum_settings is None or forum_settings.next_forum_at is None:
        logger.debug("No forum date set, skipping forum notebook reminder")
        return

    next_forum_at = forum_settings.next_forum_at
    if not is_tomorrow(next_forum_at):
        return

    # Check for duplicate: was reminder already sent for this forum date?
    already_sent = await _check_forum_reminder_already_sent(next_forum_at)
    if already_sent:
        logger.debug("Forum notebook reminder already sent for %s", next_forum_at)
        return

    logger.info("Sending forum notebook reminders for forum at %s", next_forum_at)

    # Send group message
    try:
        await bot.send_message(chat_id=config.group_chat_id, text=FORUM_NOTEBOOK_GROUP_MESSAGE)
        await _log_reminder(
            reminder_type="forum_notebook_group",
            status="sent",
        )
    except Exception as exc:
        error_msg = str(exc)
        logger.error("Failed to send forum group reminder: %s", error_msg)
        await _log_reminder(
            reminder_type="forum_notebook_group",
            status="failed",
            error_message=error_msg,
        )

    # Send private messages to all users
    users = await get_all_users_with_active_commitments()
    # Also try to notify all known users, not just those with commitments
    all_users = await _get_all_users()
    seen_ids = {u.telegram_id for u in users}
    for u in all_users:
        if u.telegram_id not in seen_ids:
            users.append(u)
            seen_ids.add(u.telegram_id)

    for user in users:
        try:
            await bot.send_message(
                chat_id=user.telegram_id,
                text=FORUM_NOTEBOOK_PRIVATE_MESSAGE,
            )
            await _log_reminder(
                reminder_type="forum_notebook_private",
                status="sent",
                telegram_user_id=user.telegram_id,
            )
        except Exception as exc:
            error_msg = str(exc)
            logger.error("Failed to send forum private reminder to user=%d: %s", user.telegram_id, error_msg)
            await _log_reminder(
                reminder_type="forum_notebook_private",
                status="failed",
                telegram_user_id=user.telegram_id,
                error_message=error_msg,
            )
            await _notify_moderator(
                bot,
                f"Не удалось отправить напоминание о форуме пользователю {user.telegram_id}: {error_msg}"
            )


async def _check_forum_reminder_already_sent(next_forum_at: datetime) -> bool:
    """Check if forum group reminder was already sent for this forum date."""
    try:
        from sqlalchemy import and_

        # We consider "same day" as already sent
        forum_date = next_forum_at.date() if hasattr(next_forum_at, 'date') else next_forum_at

        async with get_session() as session:
            result = await session.execute(
                select(ReminderLog).where(
                    ReminderLog.reminder_type == "forum_notebook_group",
                    ReminderLog.status == "sent",
                )
                .order_by(ReminderLog.sent_at.desc())
                .limit(1)
            )
            last_log = result.scalar_one_or_none()
            if last_log is None:
                return False

            # Check if sent_at date matches the day before forum
            from app.utils.dates import get_timezone
            import pytz
            tz = get_timezone()
            sent_at = last_log.sent_at
            if sent_at.tzinfo is None:
                sent_at = tz.localize(sent_at)
            else:
                sent_at = sent_at.astimezone(tz)

            next_forum_local = next_forum_at
            if next_forum_local.tzinfo is None:
                next_forum_local = tz.localize(next_forum_local)
            else:
                next_forum_local = next_forum_local.astimezone(tz)

            from datetime import timedelta
            day_before = (next_forum_local - timedelta(days=1)).date()
            return sent_at.date() == day_before
    except Exception as exc:
        logger.error("Error checking forum reminder log: %s", exc)
        return False


async def _get_all_users() -> list[User]:
    async with get_session() as session:
        result = await session.execute(select(User))
        return list(result.scalars().all())


async def _notify_moderator(bot, message: str) -> None:
    try:
        await bot.send_message(chat_id=config.moderator_telegram_id, text=f"⚠️ {message}")
    except Exception as exc:
        logger.error("Failed to notify moderator: %s", exc)
