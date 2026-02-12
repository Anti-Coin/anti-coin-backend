from datetime import datetime, timedelta, timezone

import pytest

from utils.freshness import classify_freshness, parse_utc_timestamp


def test_parse_utc_timestamp_accepts_z_suffix():
    parsed = parse_utc_timestamp("2026-02-10T15:00:00Z")
    assert parsed == datetime(2026, 2, 10, 15, 0, tzinfo=timezone.utc)


def test_parse_utc_timestamp_returns_none_on_invalid_input():
    assert parse_utc_timestamp("not-a-timestamp") is None
    assert parse_utc_timestamp(None) is None


def test_classify_freshness_returns_fresh_stale_hard_stale():
    now = datetime(2026, 2, 10, 12, 0, tzinfo=timezone.utc)
    soft = timedelta(minutes=10)
    hard = timedelta(minutes=20)

    fresh = classify_freshness(now - timedelta(minutes=5), now, soft, hard)
    stale = classify_freshness(now - timedelta(minutes=15), now, soft, hard)
    hard_stale = classify_freshness(now - timedelta(minutes=25), now, soft, hard)

    assert fresh.status == "fresh"
    assert stale.status == "stale"
    assert hard_stale.status == "hard_stale"


def test_classify_freshness_clamps_future_updated_at_to_zero_age():
    now = datetime(2026, 2, 10, 12, 0, tzinfo=timezone.utc)
    result = classify_freshness(
        updated_at=now + timedelta(minutes=5),
        now=now,
        soft_limit=timedelta(minutes=10),
    )
    assert result.status == "fresh"
    assert result.age == timedelta(0)


def test_classify_freshness_rejects_invalid_limits():
    now = datetime(2026, 2, 10, 12, 0, tzinfo=timezone.utc)
    with pytest.raises(ValueError):
        classify_freshness(now, now, timedelta(minutes=0))
    with pytest.raises(ValueError):
        classify_freshness(now, now, timedelta(minutes=10), timedelta(minutes=5))
