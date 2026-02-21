from datetime import timedelta

import pytest

from utils.config import (
    _enforce_ingest_timeframe_guard,
    _normalize_and_validate_symbols,
    _parse_bool_env,
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


def test_normalize_and_validate_symbols_normalizes_and_deduplicates():
    parsed = _normalize_and_validate_symbols(
        [" btc/usdt ", "ETH/USDT", "btc/usdt", "xrp/usdt"],
        env_name="TARGET_SYMBOLS",
    )
    assert parsed == ["BTC/USDT", "ETH/USDT", "XRP/USDT"]


def test_normalize_and_validate_symbols_rejects_invalid_shape():
    with pytest.raises(ValueError):
        _normalize_and_validate_symbols(
            ["BTCUSDT", "ETH/USDT"],
            env_name="TARGET_SYMBOLS",
        )


def test_normalize_and_validate_symbols_accepts_canary_addition():
    parsed = _normalize_and_validate_symbols(
        ["BTC/USDT", "ETH/USDT", "ADA/USDT"],
        env_name="TARGET_SYMBOLS",
    )
    assert parsed == ["BTC/USDT", "ETH/USDT", "ADA/USDT"]


def test_parse_bool_env_parses_common_values():
    assert _parse_bool_env("true") is True
    assert _parse_bool_env("1") is True
    assert _parse_bool_env("on") is True
    assert _parse_bool_env("false") is False
    assert _parse_bool_env("0") is False
    assert _parse_bool_env("off") is False


def test_parse_bool_env_falls_back_to_default_for_invalid():
    assert _parse_bool_env("not-a-bool", default=False) is False
    assert _parse_bool_env("not-a-bool", default=True) is True
    assert _parse_bool_env(None, default=True) is True


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


def test_enforce_ingest_timeframe_guard_accepts_only_1h_in_default_mode():
    assert _enforce_ingest_timeframe_guard(["1h"], allow_multi=False) == ["1h"]


def test_enforce_ingest_timeframe_guard_rejects_non_1h_in_default_mode():
    with pytest.raises(ValueError) as excinfo:
        _enforce_ingest_timeframe_guard(["4h"], allow_multi=False)
    message = str(excinfo.value)
    assert "ENABLE_MULTI_TIMEFRAMES=false" in message
    assert "before Phase B" not in message


def test_enforce_ingest_timeframe_guard_rejects_multiple_in_default_mode():
    with pytest.raises(ValueError):
        _enforce_ingest_timeframe_guard(["1h", "4h"], allow_multi=False)


def test_enforce_ingest_timeframe_guard_accepts_multiple_when_enabled():
    assert _enforce_ingest_timeframe_guard(
        ["1m", "1h", "1d"], allow_multi=True
    ) == [
        "1m",
        "1h",
        "1d",
    ]
