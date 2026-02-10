from datetime import datetime, timezone

import pytest

from utils.time_alignment import (
    next_timeframe_boundary,
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
