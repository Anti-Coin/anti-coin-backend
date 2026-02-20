import os
import re
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
    "1w": 8 * 24 * 60,
    "1M": 35 * 24 * 60,
}
DEFAULT_FRESHNESS_HARD_THRESHOLD_MINUTES = {
    "1h": 130,
    "4h": 500,
    "1d": 50 * 60,
    "1w": 16 * 24 * 60,
    "1M": 70 * 24 * 60,
}

SYMBOL_PATTERN = re.compile(r"^[A-Z0-9]+/[A-Z0-9]+$")


def _parse_csv_env(raw: str | None, default: list[str]) -> list[str]:
    if not raw:
        return default.copy()

    values = [item.strip() for item in raw.split(",") if item.strip()]
    return values or default.copy()


def _normalize_and_validate_symbols(
    symbols: list[str], *, env_name: str
) -> list[str]:
    """
    TARGET_SYMBOLS 계열 입력을 정규화/검증한다.

    Rules:
    - 대문자 통일 (binance spot symbol 관례)
    - 형식 강제: BASE/QUOTE (알파벳+숫자)
    - 중복 제거(입력 순서 유지)
    """
    if not symbols:
        raise ValueError(f"{env_name} must not be empty.")

    normalized: list[str] = []
    seen: set[str] = set()
    invalid: list[str] = []

    for raw_symbol in symbols:
        symbol = raw_symbol.strip().upper()
        if not SYMBOL_PATTERN.fullmatch(symbol):
            invalid.append(raw_symbol)
            continue
        if symbol in seen:
            continue
        seen.add(symbol)
        normalized.append(symbol)

    if invalid:
        rendered = ", ".join(invalid)
        raise ValueError(
            f"{env_name} contains invalid symbol(s): {rendered}. "
            "Expected format like BTC/USDT."
        )
    if not normalized:
        raise ValueError(f"{env_name} resolved to empty after normalization.")
    return normalized


def _parse_bool_env(raw: str | None, default: bool = False) -> bool:
    if raw is None:
        return default

    normalized = raw.strip().lower()
    if normalized in {"1", "true", "yes", "on"}:
        return True
    if normalized in {"0", "false", "no", "off"}:
        return False
    return default


def _parse_thresholds(
    raw: str | None, defaults: dict[str, int]
) -> dict[str, timedelta]:
    thresholds = {
        timeframe: timedelta(minutes=minutes)
        for timeframe, minutes in defaults.items()
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


def _enforce_ingest_timeframe_guard(
    timeframes: list[str], *, allow_multi: bool
) -> list[str]:
    """
    기본값은 Phase A 가드(1h 고정)이며, allow_multi=true일 때만 다중 timeframe을 허용한다.
    """
    if not timeframes:
        raise ValueError("INGEST_TIMEFRAMES must not be empty.")

    if allow_multi:
        return timeframes.copy()

    if len(timeframes) != 1 or timeframes[0] != PHASE_A_FIXED_TIMEFRAME:
        rendered = ",".join(timeframes) if timeframes else "(empty)"
        raise ValueError(
            "INGEST_TIMEFRAMES must be exactly '1h' before Phase B "
            "(set ENABLE_MULTI_TIMEFRAMES=true to allow multiple timeframes). "
            f"Got: {rendered}"
        )
    return timeframes.copy()


TARGET_SYMBOLS = _normalize_and_validate_symbols(
    _parse_csv_env(os.getenv("TARGET_SYMBOLS"), DEFAULT_TARGET_SYMBOLS),
    env_name="TARGET_SYMBOLS",
)
ENABLE_MULTI_TIMEFRAMES = _parse_bool_env(
    os.getenv("ENABLE_MULTI_TIMEFRAMES"),
    default=False,
)
INGEST_TIMEFRAMES = _enforce_ingest_timeframe_guard(
    _parse_csv_env(os.getenv("INGEST_TIMEFRAMES"), DEFAULT_INGEST_TIMEFRAMES),
    allow_multi=ENABLE_MULTI_TIMEFRAMES,
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
