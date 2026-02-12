from datetime import datetime, timedelta, timezone

import pandas as pd

from scripts.pipeline_worker import (
    _detect_gaps_from_ms_timestamps,
    _fetch_ohlcv_paginated,
    _refill_detected_gaps,
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
