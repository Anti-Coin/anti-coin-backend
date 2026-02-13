import os
from datetime import timedelta

DEFAULT_TARGET_SYMBOLS = [
    "BTC/USDT",
    "ETH/USDT",
    "XRP/USDT",
    "SOL/USDT",
    "DOGE/USDT",
]
DEFAULT_INGEST_TIMEFRAMES = ["1h"]
PHASE_A_FIXED_TIMEFRAME = "1h"
DEFAULT_FRESHNESS_THRESHOLD_MINUTES = {
    "1h": 65,
    "4h": 250,
    "1d": 25 * 60,
}
DEFAULT_FRESHNESS_HARD_THRESHOLD_MINUTES = {
    "1h": 130,
    "4h": 500,
    "1d": 50 * 60,
}


def _parse_csv_env(raw: str | None, default: list[str]) -> list[str]:
    if not raw:
        return default.copy()

    values = [item.strip() for item in raw.split(",") if item.strip()]
    return values or default.copy()


def _parse_thresholds(
    raw: str | None, defaults: dict[str, int]
) -> dict[str, timedelta]:
    thresholds = {
        timeframe: timedelta(minutes=minutes) for timeframe, minutes in defaults.items()
    }
    if not raw:
        return thresholds

    # Format: "1h:65,4h:250,1d:1500"
    for chunk in raw.split(","):
        if ":" not in chunk:
            continue
        timeframe, minute_text = chunk.split(":", 1)
        timeframe = timeframe.strip()
        minute_text = minute_text.strip()
        if not timeframe or not minute_text:
            continue
        try:
            thresholds[timeframe] = timedelta(minutes=int(minute_text))
        except ValueError:
            continue

    return thresholds


def _enforce_phase_a_timeframe_guard(timeframes: list[str]) -> list[str]:
    """
    Phase B 이전에는 운영 타임프레임을 1h로 고정한다.
    """
    if len(timeframes) != 1 or timeframes[0] != PHASE_A_FIXED_TIMEFRAME:
        rendered = ",".join(timeframes) if timeframes else "(empty)"
        raise ValueError(
            "INGEST_TIMEFRAMES must be exactly '1h' before Phase B. " f"Got: {rendered}"
        )
    return timeframes.copy()


TARGET_SYMBOLS = _parse_csv_env(os.getenv("TARGET_SYMBOLS"), DEFAULT_TARGET_SYMBOLS)
INGEST_TIMEFRAMES = _enforce_phase_a_timeframe_guard(
    _parse_csv_env(os.getenv("INGEST_TIMEFRAMES"), DEFAULT_INGEST_TIMEFRAMES)
)
PRIMARY_TIMEFRAME = (
    INGEST_TIMEFRAMES[0] if INGEST_TIMEFRAMES else DEFAULT_INGEST_TIMEFRAMES[0]
)
FRESHNESS_THRESHOLDS = _parse_thresholds(
    os.getenv("FRESHNESS_THRESHOLDS_MINUTES"),
    DEFAULT_FRESHNESS_THRESHOLD_MINUTES,
)
FRESHNESS_HARD_THRESHOLDS = _parse_thresholds(
    os.getenv("FRESHNESS_HARD_THRESHOLDS_MINUTES"),
    DEFAULT_FRESHNESS_HARD_THRESHOLD_MINUTES,
)
