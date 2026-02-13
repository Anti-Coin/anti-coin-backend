from dataclasses import dataclass
from datetime import datetime, timedelta, timezone


@dataclass(frozen=True)
class FreshnessResult:
    status: str
    age: timedelta
    soft_limit: timedelta
    hard_limit: timedelta


def parse_utc_timestamp(value: str | None) -> datetime | None:
    """utc로 통일하기 위한 함수"""
    if not value or not isinstance(value, str):
        return None

    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None

    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)

    return parsed.astimezone(timezone.utc)


def classify_freshness(
    updated_at: datetime,
    now: datetime,
    soft_limit: timedelta,
    hard_limit: timedelta | None = None,
) -> FreshnessResult:
    """데이터의 최신 상태를 판단하는 함수"""
    if soft_limit <= timedelta(0):
        raise ValueError("soft_limit must be positive.")

    resolved_hard_limit = hard_limit or soft_limit * 2
    if resolved_hard_limit < soft_limit:
        raise ValueError(
            "hard_limit must be greater than or equal to soft_limit."
        )

    age = now - updated_at
    if age < timedelta(0):
        age = timedelta(0)

    if age <= soft_limit:
        status = "fresh"
    elif age <= resolved_hard_limit:
        status = "stale"
    else:
        status = "hard_stale"

    return FreshnessResult(
        status=status,
        age=age,
        soft_limit=soft_limit,
        hard_limit=resolved_hard_limit,
    )
