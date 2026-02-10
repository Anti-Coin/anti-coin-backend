import json
import os
import time
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path

import requests

from utils.config import (
    FRESHNESS_HARD_THRESHOLDS,
    FRESHNESS_THRESHOLDS,
    INGEST_TIMEFRAMES,
    TARGET_SYMBOLS,
)
from utils.freshness import classify_freshness, parse_utc_timestamp
from utils.logger import get_logger

logger = get_logger(__name__)

DISCORD_WEBHOOK_URL = os.getenv("DISCORD_WEBHOOK_URL", "")
STATIC_DATA_DIR = Path(os.getenv("STATIC_DATA_DIR", "/app/static_data"))


def _parse_positive_int_env(name: str, default: int) -> int:
    raw = os.getenv(name)
    if raw is None:
        return default

    try:
        value = int(raw)
        return value if value > 0 else default
    except ValueError:
        return default


MONITOR_POLL_SECONDS = _parse_positive_int_env("MONITOR_POLL_SECONDS", 60)

HEALTHY_STATUSES = {"fresh", "stale"}
ALERTABLE_UNHEALTHY_STATUSES = {"hard_stale", "corrupt", "missing"}


@dataclass(frozen=True)
class MonitorSnapshot:
    symbol: str
    timeframe: str
    status: str
    detail: str
    updated_at: str | None = None
    age_minutes: float | None = None


@dataclass(frozen=True)
class MonitorAlertEvent:
    key: str
    symbol: str
    timeframe: str
    event: str
    previous_status: str | None
    current_snapshot: MonitorSnapshot


def _safe_symbol(symbol: str) -> str:
    return symbol.replace("/", "_")


def prediction_file_candidates(
    symbol: str, timeframe: str, static_dir: Path = STATIC_DATA_DIR
) -> list[Path]:
    """prediction file 목록을 반환. 1h의 경우 legacy 파일을 포함"""
    safe_symbol = _safe_symbol(symbol)
    timeframe_file = static_dir / f"prediction_{safe_symbol}_{timeframe}.json"

    if timeframe == "1h":
        legacy_file = static_dir / f"prediction_{safe_symbol}.json"
        return [timeframe_file, legacy_file]

    return [timeframe_file]


def _read_prediction_file(file_path: Path) -> dict | None:
    try:
        with open(file_path, "r") as f:
            return json.load(f)
    except json.JSONDecodeError:
        return None
    except OSError as e:
        logger.error(f"Failed to read file {file_path}: {e}")
        return None


def evaluate_symbol_timeframe(
    symbol: str,
    timeframe: str,
    now: datetime | None = None,
    static_dir: Path = STATIC_DATA_DIR,
    soft_thresholds: dict[str, timedelta] | None = None,
    hard_thresholds: dict[str, timedelta] | None = None,
) -> MonitorSnapshot:
    resolved_now = now or datetime.now(timezone.utc)
    resolved_soft = soft_thresholds or FRESHNESS_THRESHOLDS
    resolved_hard = hard_thresholds or FRESHNESS_HARD_THRESHOLDS

    default_soft = resolved_soft.get("1h", timedelta(minutes=65))
    default_hard = resolved_hard.get("1h", default_soft * 2)
    soft_limit = resolved_soft.get(timeframe, default_soft)
    hard_limit = resolved_hard.get(timeframe, max(default_hard, soft_limit * 2))

    # Prediction 파일을 순회
    for file_path in prediction_file_candidates(symbol, timeframe, static_dir):
        if not file_path.exists():
            continue

        payload = _read_prediction_file(file_path)
        if payload is None:  # 파일을 읽는 과정에서 Error -> corrupt
            return MonitorSnapshot(
                symbol=symbol,
                timeframe=timeframe,
                status="corrupt",
                detail=f"JSON decode error: {file_path.name}",
            )

        updated_at_str = payload.get("updated_at")
        updated_at = parse_utc_timestamp(updated_at_str)
        if updated_at is None:  # updated_at이 없음 -> corrupt
            return MonitorSnapshot(
                symbol=symbol,
                timeframe=timeframe,
                status="corrupt",
                detail=f"Invalid updated_at format: {file_path.name}",
            )

        freshness = classify_freshness(
            updated_at=updated_at,
            now=resolved_now,
            soft_limit=soft_limit,
            hard_limit=hard_limit,
        )
        return MonitorSnapshot(
            symbol=symbol,
            timeframe=timeframe,
            status=freshness.status,
            detail=f"checked={file_path.name}",
            updated_at=updated_at.strftime("%Y-%m-%dT%H:%M:%SZ"),
            age_minutes=round(freshness.age.total_seconds() / 60, 2),
        )

    # 파일이 없음
    return MonitorSnapshot(
        symbol=symbol,
        timeframe=timeframe,
        status="missing",
        detail="Prediction file is missing.",
    )


def detect_alert_event(previous_status: str | None, current_status: str) -> str | None:
    """
    fresh, stale -> hard_stale, corrupt, missing => alert
    hard_stale, corrupt, missing -> fresh, stale => recovery
    """
    if (
        current_status in ALERTABLE_UNHEALTHY_STATUSES
        and previous_status != current_status
    ):
        return current_status

    if (
        previous_status in ALERTABLE_UNHEALTHY_STATUSES
        and current_status in HEALTHY_STATUSES
    ):
        return "recovery"

    return None


def run_monitor_cycle(
    state: dict[str, MonitorSnapshot],
    now: datetime | None = None,
    symbols: list[str] | None = None,
    timeframes: list[str] | None = None,
    static_dir: Path = STATIC_DATA_DIR,
    soft_thresholds: dict[str, timedelta] | None = None,
    hard_thresholds: dict[str, timedelta] | None = None,
) -> list[MonitorAlertEvent]:
    resolved_now = now or datetime.now(timezone.utc)
    resolved_symbols = symbols or TARGET_SYMBOLS
    resolved_timeframes = timeframes or INGEST_TIMEFRAMES
    events: list[MonitorAlertEvent] = []

    for symbol in resolved_symbols:
        for timeframe in resolved_timeframes:
            key = f"{symbol}|{timeframe}"
            snapshot = evaluate_symbol_timeframe(
                symbol=symbol,
                timeframe=timeframe,
                now=resolved_now,
                static_dir=static_dir,
                soft_thresholds=soft_thresholds,
                hard_thresholds=hard_thresholds,
            )
            previous_status = state.get(key).status if key in state else None
            event = detect_alert_event(previous_status, snapshot.status)
            if event:
                events.append(
                    MonitorAlertEvent(
                        key=key,
                        symbol=symbol,
                        timeframe=timeframe,
                        event=event,
                        previous_status=previous_status,
                        current_snapshot=snapshot,
                    )
                )

            state[key] = snapshot
            logger.info(
                f"[Monitor] {symbol} {timeframe} status={snapshot.status} detail={snapshot.detail}"
            )

    return events


def send_discord_alert(event: MonitorAlertEvent) -> None:
    message = (
        f"[{event.event.upper()}] {event.symbol} {event.timeframe}\n"
        f"prev={event.previous_status} -> now={event.current_snapshot.status}\n"
        f"detail={event.current_snapshot.detail}\n"
        f"updated_at={event.current_snapshot.updated_at}\n"
        f"age_minutes={event.current_snapshot.age_minutes}"
    )

    if not DISCORD_WEBHOOK_URL:
        logger.info(f"[Alert Ignored] {message}")
        return

    try:
        payload = {"content": f"**Coin Predict Monitor Alert**\n```{message}```"}
        response = requests.post(DISCORD_WEBHOOK_URL, json=payload, timeout=5)
        response.raise_for_status()
    except Exception as e:
        logger.error(f"Failed to send monitor alert: {e}")


def run_monitor() -> None:
    logger.info(
        f"[Status Monitor] started. symbols={TARGET_SYMBOLS}, timeframes={INGEST_TIMEFRAMES}, poll={MONITOR_POLL_SECONDS}s"
    )

    state: dict[str, MonitorSnapshot] = {}
    while True:
        cycle_start = time.time()
        try:
            events = run_monitor_cycle(state)
            for event in events:
                send_discord_alert(event)
        except Exception as e:
            logger.error(f"Status monitor cycle error: {e}")

        elapsed = time.time() - cycle_start
        sleep_for = max(1.0, MONITOR_POLL_SECONDS - elapsed)
        time.sleep(sleep_for)


if __name__ == "__main__":
    run_monitor()
