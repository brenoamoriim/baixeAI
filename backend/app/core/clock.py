"""Time helpers. Everything is stored in UTC; the business day uses America/Sao_Paulo."""

import calendar
from datetime import UTC, date, datetime, time, timedelta
from zoneinfo import ZoneInfo

from app.core.config import get_settings

_override: datetime | None = None


def now() -> datetime:
    """Current UTC time. Tests may freeze it with `freeze()`."""
    return _override if _override is not None else datetime.now(UTC)


def freeze(moment: datetime | None) -> None:
    global _override
    if moment is not None and moment.tzinfo is None:
        raise ValueError("frozen time must be timezone-aware")
    _override = moment


def local_tz() -> ZoneInfo:
    return ZoneInfo(get_settings().tz_reference)


def local_date(moment: datetime | None = None) -> date:
    return (moment or now()).astimezone(local_tz()).date()


def local_day_bounds(day: date) -> tuple[datetime, datetime]:
    """UTC start/end of a business day (00:00 to next 00:00 in the reference zone)."""
    tz = local_tz()
    start = datetime.combine(day, time.min, tzinfo=tz)
    end = datetime.combine(day + timedelta(days=1), time.min, tzinfo=tz)
    return start.astimezone(UTC), end.astimezone(UTC)


def add_months(moment: datetime, months: int = 1) -> datetime:
    """Calendar month addition, clamped to the last day of the target month (31/01 -> 28/02)."""
    month_index = moment.month - 1 + months
    year = moment.year + month_index // 12
    month = month_index % 12 + 1
    day = min(moment.day, calendar.monthrange(year, month)[1])
    return moment.replace(year=year, month=month, day=day)
