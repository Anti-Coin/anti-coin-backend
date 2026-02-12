from datetime import datetime, timezone

import pytest

from utils.time_alignment import (
    detect_timeframe_gaps,
    last_closed_candle_open,
    next_timeframe_boundary,
    timeframe_to_timedelta,
    timeframe_to_pandas_freq,
)


def test_next_timeframe_boundary_for_1h():
    now = datetime(2026, 2, 10, 10, 37, 12, tzinfo=timezone.utc)
    assert next_timeframe_boundary(now, "1h") == datetime(
        2026, 2, 10, 11, 0, 0, tzinfo=timezone.utc
    )


def test_next_timeframe_boundary_for_4h():
    now = datetime(2026, 2, 10, 10, 37, 0, tzinfo=timezone.utc)
    assert next_timeframe_boundary(now, "4h") == datetime(
        2026, 2, 10, 12, 0, 0, tzinfo=timezone.utc
    )


def test_next_timeframe_boundary_moves_forward_when_exact_boundary():
    now = datetime(2026, 2, 10, 10, 0, 0, tzinfo=timezone.utc)
    assert next_timeframe_boundary(now, "1h") == datetime(
        2026, 2, 10, 11, 0, 0, tzinfo=timezone.utc
    )


def test_next_timeframe_boundary_for_1d_1w_1M():
    now = datetime(2026, 2, 10, 10, 37, 0, tzinfo=timezone.utc)  # Tuesday
    assert next_timeframe_boundary(now, "1d") == datetime(
        2026, 2, 11, 0, 0, 0, tzinfo=timezone.utc
    )
    assert next_timeframe_boundary(now, "1w") == datetime(
        2026, 2, 16, 0, 0, 0, tzinfo=timezone.utc
    )
    assert next_timeframe_boundary(now, "1M") == datetime(
        2026, 3, 1, 0, 0, 0, tzinfo=timezone.utc
    )


def test_next_timeframe_boundary_rejects_invalid_format():
    now = datetime(2026, 2, 10, 10, 37, 0, tzinfo=timezone.utc)
    with pytest.raises(ValueError):
        next_timeframe_boundary(now, "hourly")


def test_timeframe_to_pandas_freq_mapping():
    assert timeframe_to_pandas_freq("1h") == "1h"
    assert timeframe_to_pandas_freq("4h") == "4h"
    assert timeframe_to_pandas_freq("15m") == "15min"
    assert timeframe_to_pandas_freq("1d") == "1D"
    assert timeframe_to_pandas_freq("1w") == "1W-MON"
    assert timeframe_to_pandas_freq("1M") == "1MS"


def test_last_closed_candle_open_for_1h_inside_bucket():
    now = datetime(2026, 2, 10, 10, 37, 12, tzinfo=timezone.utc)
    assert last_closed_candle_open(now, "1h") == datetime(
        2026, 2, 10, 9, 0, 0, tzinfo=timezone.utc
    )


def test_last_closed_candle_open_for_1h_exact_boundary():
    now = datetime(2026, 2, 10, 11, 0, 0, tzinfo=timezone.utc)
    assert last_closed_candle_open(now, "1h") == datetime(
        2026, 2, 10, 10, 0, 0, tzinfo=timezone.utc
    )


def test_last_closed_candle_open_for_1d_1w_1M():
    now = datetime(2026, 2, 10, 10, 37, 0, tzinfo=timezone.utc)  # Tuesday
    assert last_closed_candle_open(now, "1d") == datetime(
        2026, 2, 9, 0, 0, 0, tzinfo=timezone.utc
    )
    assert last_closed_candle_open(now, "1w") == datetime(
        2026, 2, 2, 0, 0, 0, tzinfo=timezone.utc
    )
    assert last_closed_candle_open(now, "1M") == datetime(
        2026, 1, 1, 0, 0, 0, tzinfo=timezone.utc
    )


def test_detect_timeframe_gaps_returns_empty_on_continuous_series():
    opens = [
        datetime(2026, 2, 10, 0, 0, tzinfo=timezone.utc),
        datetime(2026, 2, 10, 1, 0, tzinfo=timezone.utc),
        datetime(2026, 2, 10, 2, 0, tzinfo=timezone.utc),
    ]
    assert detect_timeframe_gaps(opens, "1h") == []


def test_detect_timeframe_gaps_identifies_missing_windows():
    opens = [
        datetime(2026, 2, 10, 0, 0, tzinfo=timezone.utc),
        datetime(2026, 2, 10, 1, 0, tzinfo=timezone.utc),
        datetime(2026, 2, 10, 4, 0, tzinfo=timezone.utc),
    ]
    gaps = detect_timeframe_gaps(opens, "1h")

    assert len(gaps) == 1
    assert gaps[0].start_open == datetime(2026, 2, 10, 2, 0, tzinfo=timezone.utc)
    assert gaps[0].end_open == datetime(2026, 2, 10, 3, 0, tzinfo=timezone.utc)
    assert gaps[0].missing_count == 2


def test_detect_timeframe_gaps_handles_unsorted_and_duplicate_timestamps():
    opens = [
        datetime(2026, 2, 10, 3, 0, tzinfo=timezone.utc),
        datetime(2026, 2, 10, 1, 0, tzinfo=timezone.utc),
        datetime(2026, 2, 10, 1, 0, tzinfo=timezone.utc),
    ]
    gaps = detect_timeframe_gaps(opens, "1h")
    assert len(gaps) == 1
    assert gaps[0].missing_count == 1


def test_timeframe_to_timedelta_rejects_month_timeframe():
    with pytest.raises(ValueError):
        timeframe_to_timedelta("1M")
