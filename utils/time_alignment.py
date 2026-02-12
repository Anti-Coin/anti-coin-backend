import re
from dataclasses import dataclass
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


def last_closed_candle_open(now: datetime, timeframe: str) -> datetime:
    """
    Return the open timestamp of the latest fully closed candle in UTC.
    Example:
      - now=10:37, timeframe=1h -> 09:00
      - now=11:00, timeframe=1h -> 10:00
    """
    value, unit = _parse_timeframe(timeframe)
    now_utc = _to_utc(now)

    if unit in {"m", "h"}:
        step_seconds = value * (60 if unit == "m" else 3600)
        now_seconds = int(now_utc.timestamp())
        current_open_seconds = (now_seconds // step_seconds) * step_seconds
        last_closed_open_seconds = current_open_seconds - step_seconds
        return datetime.fromtimestamp(
            last_closed_open_seconds, tz=timezone.utc
        )

    if unit == "d":
        anchor = datetime(1970, 1, 1, tzinfo=timezone.utc)
        current_day_start = now_utc.replace(
            hour=0, minute=0, second=0, microsecond=0
        )
        elapsed_days = (current_day_start - anchor).days
        current_bucket_start_days = (elapsed_days // value) * value
        return anchor + timedelta(days=current_bucket_start_days - value)

    if unit == "w":
        anchor = datetime(1970, 1, 5, tzinfo=timezone.utc)  # Monday
        current_week_start = (
            now_utc - timedelta(days=now_utc.weekday())
        ).replace(hour=0, minute=0, second=0, microsecond=0)
        elapsed_weeks = (current_week_start - anchor).days // 7
        current_bucket_start_weeks = (elapsed_weeks // value) * value
        return anchor + timedelta(
            weeks=current_bucket_start_weeks - value
        )

    # unit == "M"
    current_month_start = now_utc.replace(
        day=1, hour=0, minute=0, second=0, microsecond=0
    )
    month_index = current_month_start.year * 12 + (
        current_month_start.month - 1
    )
    current_bucket_start_month = (month_index // value) * value
    last_closed_open_month = current_bucket_start_month - value
    year = last_closed_open_month // 12
    month = (last_closed_open_month % 12) + 1
    return datetime(year, month, 1, tzinfo=timezone.utc)


def timeframe_to_timedelta(timeframe: str) -> timedelta:
    value, unit = _parse_timeframe(timeframe)
    if unit == "m":
        return timedelta(minutes=value)
    if unit == "h":
        return timedelta(hours=value)
    if unit == "d":
        return timedelta(days=value)
    if unit == "w":
        return timedelta(weeks=value)
    raise ValueError(
        "Gap detection does not support month-based timeframe."
    )


@dataclass(frozen=True)
class GapWindow:
    start_open: datetime
    end_open: datetime
    missing_count: int


def detect_timeframe_gaps(
    candle_opens: list[datetime], timeframe: str
) -> list[GapWindow]:
    """
    Detect missing candle windows from candle-open timestamps.
    """
    if len(candle_opens) < 2:
        return []

    step = timeframe_to_timedelta(timeframe)
    step_seconds = int(step.total_seconds())

    normalized = sorted(_to_utc(ts) for ts in candle_opens)
    deduped: list[datetime] = []
    for ts in normalized:
        if not deduped or ts != deduped[-1]:
            deduped.append(ts)

    gaps: list[GapWindow] = []
    for previous_open, current_open in zip(deduped, deduped[1:]):
        delta_seconds = int((current_open - previous_open).total_seconds())
        if delta_seconds <= step_seconds:
            continue

        missing_count = (delta_seconds // step_seconds) - 1
        if missing_count <= 0:
            continue

        gap_start = previous_open + step
        gap_end = current_open - step
        gaps.append(
            GapWindow(
                start_open=gap_start,
                end_open=gap_end,
                missing_count=missing_count,
            )
        )

    return gaps


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
