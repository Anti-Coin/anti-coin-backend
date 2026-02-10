import re
from datetime import datetime, timedelta, timezone

_TIMEFRAME_PATTERN = re.compile(r"^(?P<value>\d+)(?P<unit>[mhdwM])$")


def _parse_timeframe(timeframe: str) -> tuple[int, str]:
    match = _TIMEFRAME_PATTERN.match(timeframe)
    if not match:
        raise ValueError(
            f"Unsupported timeframe format: {timeframe!r}. Expected like '1h', '4h', '1d'."
        )

    value = int(match.group("value"))
    unit = match.group("unit")
    if value <= 0:
        raise ValueError("Timeframe value must be positive.")
    return value, unit


def _to_utc(dt: datetime) -> datetime:
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def next_timeframe_boundary(now: datetime, timeframe: str) -> datetime:
    """
    Return the next boundary strictly after `now` in UTC.
    Example: now=10:37, timeframe=1h -> 11:00.
    """
    value, unit = _parse_timeframe(timeframe)
    now_utc = _to_utc(now)

    if unit in {"m", "h"}:
        step_seconds = value * (60 if unit == "m" else 3600)
        now_seconds = int(now_utc.timestamp())
        next_seconds = ((now_seconds // step_seconds) + 1) * step_seconds
        return datetime.fromtimestamp(next_seconds, tz=timezone.utc)

    if unit == "d":
        anchor = datetime(1970, 1, 1, tzinfo=timezone.utc)
        current_day_start = now_utc.replace(
            hour=0, minute=0, second=0, microsecond=0
        )
        elapsed_days = (current_day_start - anchor).days
        next_bucket_start_days = ((elapsed_days // value) + 1) * value
        return anchor + timedelta(days=next_bucket_start_days)

    if unit == "w":
        # Week boundary: Monday 00:00 UTC
        anchor = datetime(1970, 1, 5, tzinfo=timezone.utc)  # Monday
        current_week_start = (
            now_utc - timedelta(days=now_utc.weekday())
        ).replace(hour=0, minute=0, second=0, microsecond=0)
        elapsed_weeks = (current_week_start - anchor).days // 7
        next_bucket_start_weeks = ((elapsed_weeks // value) + 1) * value
        return anchor + timedelta(weeks=next_bucket_start_weeks)

    # unit == "M"
    current_month_start = now_utc.replace(
        day=1, hour=0, minute=0, second=0, microsecond=0
    )
    month_index = current_month_start.year * 12 + (current_month_start.month - 1)
    next_month_index = ((month_index // value) + 1) * value
    year = next_month_index // 12
    month = (next_month_index % 12) + 1
    return datetime(year, month, 1, tzinfo=timezone.utc)


def timeframe_to_pandas_freq(timeframe: str) -> str:
    value, unit = _parse_timeframe(timeframe)
    if unit == "m":
        return f"{value}min"
    if unit == "h":
        return f"{value}h"
    if unit == "d":
        return f"{value}D"
    if unit == "w":
        return f"{value}W-MON"
    return f"{value}MS"
