import json
from datetime import datetime, timedelta, timezone

import pandas as pd

from scripts.pipeline_worker import (
    _detect_gaps_from_ms_timestamps,
    _fetch_ohlcv_paginated,
    _refill_detected_gaps,
    prediction_enabled_for_timeframe,
    run_prediction_and_save,
    save_history_to_json,
    upsert_prediction_health,
)


def _to_ms(dt: datetime) -> int:
    return int(dt.timestamp() * 1000)


class FakeExchange:
    def __init__(self, candles: list[list[float]]):
        self._candles = sorted(candles, key=lambda row: row[0])

    def parse_timeframe(self, timeframe: str) -> int:
        if timeframe == "1h":
            return 60 * 60
        raise ValueError("unsupported timeframe for test")

    def fetch_ohlcv(
        self, symbol: str, timeframe: str, since: int, limit: int
    ) -> list[list[float]]:
        candidates = [row for row in self._candles if row[0] >= since]
        return candidates[:limit]


def test_fetch_ohlcv_paginated_respects_until_ms():
    base = datetime(2026, 2, 12, 0, 0, tzinfo=timezone.utc)
    candles = [
        [_to_ms(base + timedelta(hours=offset)), 1.0, 1.0, 1.0, 1.0, 1.0]
        for offset in range(4)
    ]
    exchange = FakeExchange(candles)

    loaded, pages = _fetch_ohlcv_paginated(
        exchange=exchange,
        symbol="BTC/USDT",
        timeframe="1h",
        since_ms=_to_ms(base),
        until_ms=_to_ms(base + timedelta(hours=2)),
    )

    assert pages == 1
    assert loaded["timestamp"].tolist() == [
        _to_ms(base),
        _to_ms(base + timedelta(hours=1)),
        _to_ms(base + timedelta(hours=2)),
    ]


def test_refill_detected_gaps_recovers_missing_candle():
    base = datetime(2026, 2, 12, 0, 0, tzinfo=timezone.utc)
    full_candles = [
        [_to_ms(base + timedelta(hours=offset)), 1.0, 1.0, 1.0, 1.0, 1.0]
        for offset in range(4)
    ]
    exchange = FakeExchange(full_candles)

    source_df = pd.DataFrame(
        [
            full_candles[0],
            full_candles[1],
            full_candles[3],
        ],
        columns=["timestamp", "open", "high", "low", "close", "volume"],
    )
    gaps = _detect_gaps_from_ms_timestamps(
        source_df["timestamp"].tolist(), timeframe="1h"
    )

    merged, refill_pages = _refill_detected_gaps(
        exchange=exchange,
        symbol="BTC/USDT",
        timeframe="1h",
        source_df=source_df,
        gaps=gaps,
        last_closed_ms=_to_ms(base + timedelta(hours=3)),
    )

    assert refill_pages == 1
    assert merged["timestamp"].tolist() == [
        _to_ms(base),
        _to_ms(base + timedelta(hours=1)),
        _to_ms(base + timedelta(hours=2)),
        _to_ms(base + timedelta(hours=3)),
    ]


def test_upsert_prediction_health_tracks_failure_and_recovery(tmp_path):
    health_path = tmp_path / "prediction_health.json"

    first, was_degraded, is_degraded = upsert_prediction_health(
        "BTC/USDT",
        "1h",
        prediction_ok=False,
        error="model_missing",
        path=health_path,
    )
    assert was_degraded is False
    assert is_degraded is True
    assert first["consecutive_failures"] == 1
    assert first["last_success_at"] is None
    assert first["last_error"] == "model_missing"

    second, was_degraded, is_degraded = upsert_prediction_health(
        "BTC/USDT",
        "1h",
        prediction_ok=False,
        error="model_missing",
        path=health_path,
    )
    assert was_degraded is True
    assert is_degraded is True
    assert second["consecutive_failures"] == 2

    third, was_degraded, is_degraded = upsert_prediction_health(
        "BTC/USDT",
        "1h",
        prediction_ok=True,
        path=health_path,
    )
    assert was_degraded is True
    assert is_degraded is False
    assert third["consecutive_failures"] == 0
    assert third["last_success_at"] is not None
    assert third["last_failure_at"] is not None


def test_prediction_enabled_for_timeframe_respects_disabled_set(monkeypatch):
    monkeypatch.setattr(
        "scripts.pipeline_worker.PREDICTION_DISABLED_TIMEFRAMES",
        {"1m", "5m"},
    )

    assert prediction_enabled_for_timeframe("1m") is False
    assert prediction_enabled_for_timeframe("1h") is True


def test_run_prediction_and_save_skips_disabled_timeframe(monkeypatch):
    monkeypatch.setattr(
        "scripts.pipeline_worker.PREDICTION_DISABLED_TIMEFRAMES",
        {"1m"},
    )

    result, error = run_prediction_and_save(
        write_api=None,
        symbol="BTC/USDT",
        timeframe="1m",
    )
    assert result == "skipped"
    assert error is None


def test_save_history_to_json_writes_timeframe_aware_files(tmp_path, monkeypatch):
    monkeypatch.setattr("scripts.pipeline_worker.STATIC_DIR", tmp_path)

    base = datetime(2026, 2, 12, 0, 0, tzinfo=timezone.utc)
    df = pd.DataFrame(
        [
            {
                "timestamp": base,
                "open": 1.0,
                "high": 2.0,
                "low": 0.5,
                "close": 1.5,
                "volume": 10.0,
            }
        ]
    ).set_index("timestamp")

    save_history_to_json(df, "BTC/USDT", "4h")

    canonical_path = tmp_path / "history_BTC_USDT_4h.json"
    legacy_path = tmp_path / "history_BTC_USDT.json"
    assert canonical_path.exists()
    assert legacy_path.exists()

    payload = json.loads(canonical_path.read_text())
    assert payload["symbol"] == "BTC/USDT"
    assert payload["timeframe"] == "4h"
    assert payload["type"] == "history_4h"
