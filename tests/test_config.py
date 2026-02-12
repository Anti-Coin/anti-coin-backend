from datetime import timedelta

import pytest

from utils.config import (
    _enforce_phase_a_timeframe_guard,
    _parse_csv_env,
    _parse_thresholds,
)


def test_parse_csv_env_returns_default_on_empty_input():
    defaults = ["BTC/USDT"]
    assert _parse_csv_env(None, defaults) == defaults
    assert _parse_csv_env("", defaults) == defaults


def test_parse_csv_env_trims_and_filters_empty_values():
    raw = " BTC/USDT, , ETH/USDT ,,SOL/USDT "
    parsed = _parse_csv_env(raw, ["X"])
    assert parsed == ["BTC/USDT", "ETH/USDT", "SOL/USDT"]


def test_parse_thresholds_keeps_defaults_and_applies_valid_overrides():
    defaults = {"1h": 65, "1d": 1500}
    parsed = _parse_thresholds("1h:70,broken,1d:2000,4h:250", defaults)

    assert parsed["1h"] == timedelta(minutes=70)
    assert parsed["1d"] == timedelta(minutes=2000)
    assert parsed["4h"] == timedelta(minutes=250)


def test_parse_thresholds_ignores_invalid_values():
    defaults = {"1h": 65}
    parsed = _parse_thresholds("1h:not-a-number,2h:", defaults)
    assert parsed["1h"] == timedelta(minutes=65)
    assert "2h" not in parsed


def test_enforce_phase_a_timeframe_guard_accepts_only_1h():
    assert _enforce_phase_a_timeframe_guard(["1h"]) == ["1h"]


def test_enforce_phase_a_timeframe_guard_rejects_non_1h():
    with pytest.raises(ValueError):
        _enforce_phase_a_timeframe_guard(["4h"])


def test_enforce_phase_a_timeframe_guard_rejects_multiple_timeframes():
    with pytest.raises(ValueError):
        _enforce_phase_a_timeframe_guard(["1h", "4h"])
