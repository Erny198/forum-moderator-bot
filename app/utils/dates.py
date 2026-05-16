from __future__ import annotations

from datetime import datetime, date, timedelta
from typing import Optional

import pytz

from app.config import config


def get_timezone() -> pytz.BaseTzInfo:
    return pytz.timezone(config.timezone)


def now_in_tz() -> datetime:
    return datetime.now(tz=get_timezone())


def today_in_tz() -> date:
    return now_in_tz().date()


def is_tomorrow(dt: datetime) -> bool:
    tz = get_timezone()
    if dt.tzinfo is None:
        dt = tz.localize(dt)
    else:
        dt = dt.astimezone(tz)
    tomorrow = today_in_tz() + timedelta(days=1)
    return dt.date() == tomorrow


def parse_weekly_reminder_time(time_str: str) -> tuple[int, int]:
    """Parse HH:MM string and return (hour, minute)."""
    parts = time_str.split(":")
    if len(parts) != 2:
        raise ValueError(f"Invalid time format: {time_str}, expected HH:MM")
    return int(parts[0]), int(parts[1])


def day_of_week_to_int(day_name: str) -> int:
    """Convert day name to APScheduler day_of_week integer (0=Mon)."""
    mapping = {
        "MONDAY": 0,
        "TUESDAY": 1,
        "WEDNESDAY": 2,
        "THURSDAY": 3,
        "FRIDAY": 4,
        "SATURDAY": 5,
        "SUNDAY": 6,
    }
    return mapping.get(day_name.upper(), 0)


def format_datetime(dt: Optional[datetime]) -> str:
    if dt is None:
        return "не установлена"
    tz = get_timezone()
    if dt.tzinfo is None:
        dt = tz.localize(dt)
    else:
        dt = dt.astimezone(tz)
    return dt.strftime("%d.%m.%Y %H:%M")
