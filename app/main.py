from __future__ import annotations

import asyncio
import logging

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger

from app.bot import create_bot, create_dispatcher
from app.config import config
from app.database import close_db, init_db
from app.services.reminder_service import (
    send_forum_notebook_reminder,
    send_weekly_commitment_reminders,
)
from app.utils.dates import parse_weekly_reminder_time
from app.utils.logging import setup_logging

logger = logging.getLogger(__name__)


def setup_scheduler(scheduler: AsyncIOScheduler, bot) -> None:
    """Configure and add all scheduled jobs."""
    # Weekly commitment reminders
    try:
        hour, minute = parse_weekly_reminder_time(config.weekly_reminder_time)
    except ValueError as exc:
        logger.error("Invalid WEEKLY_REMINDER_TIME: %s. Using 10:00.", exc)
        hour, minute = 10, 0

    day_of_week_map = {
        "MONDAY": "mon",
        "TUESDAY": "tue",
        "WEDNESDAY": "wed",
        "THURSDAY": "thu",
        "FRIDAY": "fri",
        "SATURDAY": "sat",
        "SUNDAY": "sun",
    }
    day_of_week = day_of_week_map.get(config.weekly_reminder_day.upper(), "mon")

    scheduler.add_job(
        send_weekly_commitment_reminders,
        trigger=CronTrigger(
            day_of_week=day_of_week,
            hour=hour,
            minute=minute,
            timezone=config.timezone,
        ),
        args=[bot],
        id="weekly_commitment_reminders",
        replace_existing=True,
    )
    logger.info(
        "Scheduled weekly reminders: %s at %02d:%02d (%s)",
        config.weekly_reminder_day,
        hour,
        minute,
        config.timezone,
    )

    # Forum notebook reminder check every 30 minutes
    scheduler.add_job(
        send_forum_notebook_reminder,
        trigger=IntervalTrigger(minutes=30),
        args=[bot],
        id="forum_notebook_reminder_check",
        replace_existing=True,
    )
    logger.info("Scheduled forum notebook reminder check every 30 minutes")


async def on_startup(dispatcher, bot) -> None:
    logger.info("Starting up forum bot...")
    await init_db()
    logger.info("Database initialized")


async def on_shutdown(dispatcher, bot) -> None:
    logger.info("Shutting down forum bot...")
    await close_db()


async def main() -> None:
    setup_logging()
    logger.info("Forum bot starting up")

    bot = create_bot()
    dp = create_dispatcher()

    dp.startup.register(on_startup)
    dp.shutdown.register(on_shutdown)

    # Setup APScheduler
    scheduler = AsyncIOScheduler(timezone=config.timezone)
    setup_scheduler(scheduler, bot)
    scheduler.start()
    logger.info("Scheduler started")

    try:
        logger.info("Starting polling...")
        await dp.start_polling(bot, allowed_updates=dp.resolve_used_update_types())
    finally:
        scheduler.shutdown(wait=False)
        await bot.session.close()
        logger.info("Bot stopped")


if __name__ == "__main__":
    asyncio.run(main())
