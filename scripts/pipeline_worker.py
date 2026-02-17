import ccxt
import pandas as pd
from influxdb_client import InfluxDBClient
from influxdb_client.client.write_api import SYNCHRONOUS
from prophet.serialize import model_from_json
import json
import os
import shutil
import time
import math
from datetime import datetime, timedelta, timezone
from pathlib import Path
import requests
import traceback
from utils.logger import get_logger
from utils.config import INGEST_TIMEFRAMES, PRIMARY_TIMEFRAME, TARGET_SYMBOLS
from utils.file_io import atomic_write_json
from utils.ingest_state import IngestStateStore
from utils.prediction_status import evaluate_prediction_status
from utils.time_alignment import (
    detect_timeframe_gaps,
    last_closed_candle_open,
    next_timeframe_boundary,
    timeframe_to_pandas_freq,
)

logger = get_logger(__name__)

INFLUXDB_URL = os.getenv("INFLUXDB_URL")
INFLUXDB_TOKEN = os.getenv("INFLUXDB_TOKEN")
INFLUXDB_ORG = os.getenv("INFLUXDB_ORG")
INFLUXDB_BUCKET = os.getenv("INFLUXDB_BUCKET")

DISCORD_WEBHOOK_URL = os.getenv("DISCORD_WEBHOOK_URL", "")

BASE_DIR = Path(__file__).resolve().parent.parent
MODELS_DIR = BASE_DIR / "models"
STATIC_DIR = BASE_DIR / "static_data"
os.makedirs(MODELS_DIR, exist_ok=True)
os.makedirs(STATIC_DIR, exist_ok=True)

# 수집 대상 및 설정
TARGET_COINS = TARGET_SYMBOLS
TIMEFRAMES = INGEST_TIMEFRAMES if INGEST_TIMEFRAMES else [PRIMARY_TIMEFRAME]
LOOKBACK_DAYS = 30  # 과거 30일치 데이터 유지
INGEST_STATE_FILE = STATIC_DIR / "ingest_state.json"
PREDICTION_HEALTH_FILE = STATIC_DIR / "prediction_health.json"
MANIFEST_FILE = STATIC_DIR / "manifest.json"
DOWNSAMPLE_LINEAGE_FILE = STATIC_DIR / "downsample_lineage.json"
RUNTIME_METRICS_FILE = STATIC_DIR / "runtime_metrics.json"
SYMBOL_ACTIVATION_FILE = STATIC_DIR / "symbol_activation.json"
PREDICTION_DISABLED_TIMEFRAMES = {
    value.strip()
    for value in os.getenv("PREDICTION_DISABLED_TIMEFRAMES", "1m").split(",")
    if value.strip()
}
SERVE_ALLOWED_STATUSES = {"fresh", "stale"}
RETENTION_1M_DEFAULT_DAYS = 14
RETENTION_1M_MAX_DAYS = 30
DISK_WATERMARK_WARN_PERCENT = 70
DISK_WATERMARK_CRITICAL_PERCENT = 85
DISK_WATERMARK_BLOCK_PERCENT = 90
DISK_USAGE_PATH = Path(os.getenv("DISK_USAGE_PATH", "/"))
RETENTION_ENFORCE_INTERVAL_SECONDS = 60 * 60
DOWNSAMPLE_TARGET_TIMEFRAMES = {"1d", "1w", "1M"}
DOWNSAMPLE_SOURCE_TIMEFRAME = "1h"
DOWNSAMPLE_SOURCE_LOOKBACK_DAYS = 120
FULL_BACKFILL_TOLERANCE_HOURS = 1
CYCLE_TARGET_SECONDS = int(os.getenv("WORKER_CYCLE_SECONDS", "60"))
RUNTIME_METRICS_WINDOW_SIZE = int(
    os.getenv("RUNTIME_METRICS_WINDOW_SIZE", "240")
)
LOOKBACK_MIN_ROWS_RATIO = float(os.getenv("LOOKBACK_MIN_ROWS_RATIO", "0.8"))
WORKER_SCHEDULER_MODE = os.getenv("WORKER_SCHEDULER_MODE", "boundary").strip().lower()
VALID_WORKER_SCHEDULER_MODES = {"poll_loop", "boundary"}


def send_alert(message):
    """디스코드/슬랙 등으로 알림 전송"""
    if not DISCORD_WEBHOOK_URL:
        logger.info(f"[Alert Ignored] {message}")
        return

    try:
        payload = {"content": f"**Coin Predict Worker Alert**\n```{message}```"}
        requests.post(DISCORD_WEBHOOK_URL, json=payload, timeout=5)
    except Exception as e:
        logger.error(f"Failed to send alert: {e}")


def _prediction_health_key(symbol: str, timeframe: str) -> str:
    """prediction health 엔트리의 고유 키."""
    return f"{symbol}|{timeframe}"


def _static_export_paths(
    kind: str,
    symbol: str,
    timeframe: str,
    static_dir: Path | None = None,
) -> tuple[Path, Path | None]:
    """
    정적 산출물 파일 경로를 반환한다.

    Phase B 전환 기간에는 canonical(timeframe 포함) + legacy를 함께 유지한다.
    """
    safe_symbol = symbol.replace("/", "_")
    resolved_static_dir = static_dir or STATIC_DIR
    canonical = resolved_static_dir / f"{kind}_{safe_symbol}_{timeframe}.json"
    legacy = resolved_static_dir / f"{kind}_{safe_symbol}.json"
    if canonical == legacy:
        return canonical, None
    return canonical, legacy


def prediction_enabled_for_timeframe(timeframe: str) -> bool:
    """timeframe별 prediction 생성 허용 여부."""
    return timeframe not in PREDICTION_DISABLED_TIMEFRAMES


def _load_prediction_health(
    path: Path = PREDICTION_HEALTH_FILE,
) -> dict[str, dict]:
    """
    prediction 단계 health 상태 파일을 로드한다.

    실패 시 빈 dict를 반환한다. (worker 루프를 멈추지 않기 위한 fail-soft)
    """
    if not path.exists():
        return {}

    try:
        with open(path, "r") as f:
            payload = json.load(f)
    except (OSError, json.JSONDecodeError) as e:
        logger.error(f"Failed to load prediction health file: {e}")
        return {}

    entries = payload.get("entries")
    if not isinstance(entries, dict):
        logger.error("Invalid prediction health format: entries is not a dict.")
        return {}
    return entries


def _save_prediction_health(
    entries: dict[str, dict], path: Path = PREDICTION_HEALTH_FILE
) -> None:
    """prediction health 상태를 원자적으로 저장한다."""
    payload = {
        "version": 1,
        "updated_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "entries": entries,
    }
    atomic_write_json(path, payload, indent=2)


def _format_utc(dt: datetime | None) -> str | None:
    if dt is None:
        return None
    return dt.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _load_symbol_activation(
    path: Path = SYMBOL_ACTIVATION_FILE,
) -> dict[str, dict]:
    if not path.exists():
        return {}

    try:
        with open(path, "r") as f:
            payload = json.load(f)
    except (OSError, json.JSONDecodeError) as e:
        logger.error(f"Failed to load symbol activation file: {e}")
        return {}

    entries = payload.get("entries")
    if not isinstance(entries, dict):
        logger.error("Invalid symbol activation format: entries is not a dict.")
        return {}
    return entries


def _save_symbol_activation(
    entries: dict[str, dict], path: Path = SYMBOL_ACTIVATION_FILE
) -> None:
    payload = {
        "version": 1,
        "updated_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "entries": entries,
    }
    atomic_write_json(path, payload, indent=2)


def _remove_static_exports_for_symbol(
    symbol: str, timeframes: list[str], *, static_dir: Path = STATIC_DIR
) -> None:
    for timeframe in timeframes:
        for kind in ("history", "prediction"):
            canonical_path, legacy_path = _static_export_paths(
                kind, symbol, timeframe, static_dir=static_dir
            )
            for path in (canonical_path, legacy_path):
                if path is None:
                    continue
                try:
                    if path.exists():
                        path.unlink()
                except OSError as e:
                    logger.warning(
                        f"[{symbol} {timeframe}] failed to remove static file {path}: {e}"
                    )


def _load_runtime_metrics(path: Path = RUNTIME_METRICS_FILE) -> list[dict]:
    if not path.exists():
        return []

    try:
        with open(path, "r") as f:
            payload = json.load(f)
    except (OSError, json.JSONDecodeError) as e:
        logger.error(f"Failed to load runtime metrics file: {e}")
        return []

    entries = payload.get("recent_cycles")
    if not isinstance(entries, list):
        logger.error(
            "Invalid runtime metrics format: recent_cycles is not a list."
        )
        return []
    return entries


def _percentile(values: list[float], q: float) -> float | None:
    if not values:
        return None
    if q <= 0:
        return min(values)
    if q >= 100:
        return max(values)

    sorted_values = sorted(values)
    rank = math.ceil((q / 100) * len(sorted_values)) - 1
    rank = max(0, min(rank, len(sorted_values) - 1))
    return sorted_values[rank]


def _normalize_source_counts(raw_counts: dict | None) -> dict[str, int]:
    if not isinstance(raw_counts, dict):
        return {}

    normalized: dict[str, int] = {}
    for source, raw_count in raw_counts.items():
        if not isinstance(source, str) or not source:
            continue
        try:
            count = int(raw_count)
        except (TypeError, ValueError):
            continue
        if count <= 0:
            continue
        normalized[source] = normalized.get(source, 0) + count
    return normalized


def _aggregate_ingest_source_metrics(entries: list[dict]) -> dict[str, int | dict]:
    source_counts: dict[str, int] = {}
    rebootstrap_cycles = 0
    rebootstrap_events = 0
    underfill_guard_retrigger_cycles = 0
    underfill_guard_retrigger_events = 0

    for item in entries:
        counts = _normalize_source_counts(item.get("ingest_since_source_counts"))
        cycle_has_rebootstrap = False

        for source, count in counts.items():
            source_counts[source] = source_counts.get(source, 0) + count
            if "rebootstrap" in source:
                cycle_has_rebootstrap = True
                rebootstrap_events += count

        underfill_count = counts.get("underfilled_rebootstrap", 0)
        if underfill_count > 0:
            underfill_guard_retrigger_cycles += 1
            underfill_guard_retrigger_events += underfill_count

        if cycle_has_rebootstrap:
            rebootstrap_cycles += 1

    return {
        "source_counts": source_counts,
        "rebootstrap_cycles": rebootstrap_cycles,
        "rebootstrap_events": rebootstrap_events,
        "underfill_guard_retrigger_cycles": underfill_guard_retrigger_cycles,
        "underfill_guard_retrigger_events": underfill_guard_retrigger_events,
    }


def _aggregate_reason_counts(entries: list[dict], field_name: str) -> dict[str, int]:
    merged: dict[str, int] = {}
    for item in entries:
        counts = _normalize_source_counts(item.get(field_name))
        for reason, count in counts.items():
            merged[reason] = merged.get(reason, 0) + count
    return merged


def initialize_boundary_schedule(
    now: datetime, timeframes: list[str]
) -> dict[str, datetime]:
    return {
        timeframe: next_timeframe_boundary(now, timeframe)
        for timeframe in timeframes
    }


def resolve_boundary_due_timeframes(
    *,
    now: datetime,
    timeframes: list[str],
    next_boundary_by_timeframe: dict[str, datetime],
) -> tuple[list[str], int, datetime | None]:
    due_timeframes: list[str] = []
    missed_boundary_count = 0

    for timeframe in timeframes:
        next_boundary = next_boundary_by_timeframe.get(timeframe)
        if next_boundary is None:
            next_boundary = next_timeframe_boundary(now, timeframe)
            next_boundary_by_timeframe[timeframe] = next_boundary

        if now < next_boundary:
            continue

        due_timeframes.append(timeframe)
        boundary_advance_steps = 0
        while next_boundary <= now:
            next_boundary = next_timeframe_boundary(next_boundary, timeframe)
            boundary_advance_steps += 1

        next_boundary_by_timeframe[timeframe] = next_boundary
        missed_boundary_count += max(0, boundary_advance_steps - 1)

    next_boundary_at = (
        min(next_boundary_by_timeframe.values())
        if next_boundary_by_timeframe
        else None
    )
    return due_timeframes, missed_boundary_count, next_boundary_at


def append_runtime_cycle_metrics(
    *,
    started_at: datetime,
    elapsed_seconds: float,
    sleep_seconds: float,
    overrun: bool,
    cycle_result: str,
    error: str | None = None,
    ingest_since_source_counts: dict[str, int] | None = None,
    detection_gate_skip_counts: dict[str, int] | None = None,
    detection_gate_run_counts: dict[str, int] | None = None,
    boundary_tracking_mode: str = "poll_loop",
    missed_boundary_count: int | None = None,
    path: Path = RUNTIME_METRICS_FILE,
    target_cycle_seconds: int = CYCLE_TARGET_SECONDS,
    window_size: int = RUNTIME_METRICS_WINDOW_SIZE,
) -> dict:
    resolved_boundary_mode = (
        boundary_tracking_mode
        if boundary_tracking_mode in {"poll_loop", "boundary_scheduler"}
        else "poll_loop"
    )
    resolved_missed_boundary_count = (
        max(0, int(missed_boundary_count))
        if missed_boundary_count is not None
        else None
    )

    entries = _load_runtime_metrics(path=path)
    entry = {
        "started_at": started_at.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "elapsed_seconds": round(max(0.0, elapsed_seconds), 2),
        "sleep_seconds": round(max(0.0, sleep_seconds), 2),
        "overrun": overrun,
        "result": cycle_result,
        "error": error,
        "scheduler_mode": resolved_boundary_mode,
        "missed_boundary_count": resolved_missed_boundary_count,
        "ingest_since_source_counts": _normalize_source_counts(
            ingest_since_source_counts
        ),
        "detection_gate_skip_counts": _normalize_source_counts(
            detection_gate_skip_counts
        ),
        "detection_gate_run_counts": _normalize_source_counts(
            detection_gate_run_counts
        ),
    }
    entries.append(entry)

    effective_window = max(1, window_size)
    entries = entries[-effective_window:]

    samples = len(entries)
    success_count = sum(
        1 for item in entries if item.get("result") in {"ok", "idle"}
    )
    failure_count = samples - success_count
    overrun_count = sum(1 for item in entries if item.get("overrun") is True)
    elapsed_values = [
        float(item.get("elapsed_seconds", 0.0)) for item in entries
    ]
    sleep_values = [
        float(item.get("sleep_seconds", 0.0)) for item in entries
    ]
    avg_elapsed = (
        round(sum(elapsed_values) / samples, 2) if samples else None
    )
    avg_sleep = round(sum(sleep_values) / samples, 2) if samples else None
    p95_elapsed = _percentile(elapsed_values, 95)
    ingest_source_metrics = _aggregate_ingest_source_metrics(entries)
    detection_skip_counts = _aggregate_reason_counts(
        entries, "detection_gate_skip_counts"
    )
    detection_run_counts = _aggregate_reason_counts(
        entries, "detection_gate_run_counts"
    )
    if resolved_boundary_mode == "boundary_scheduler":
        boundary_counts = [
            max(0, int(item.get("missed_boundary_count") or 0))
            for item in entries
        ]
        missed_boundary_total = sum(boundary_counts)
        missed_boundary_rate = (
            round(missed_boundary_total / samples, 4) if samples else None
        )
    else:
        missed_boundary_total = None
        missed_boundary_rate = None

    summary = {
        "samples": samples,
        "success_count": success_count,
        "failure_count": failure_count,
        "success_rate": (
            round(success_count / samples, 4) if samples else None
        ),
        "avg_elapsed_seconds": avg_elapsed,
        "p95_elapsed_seconds": (
            round(p95_elapsed, 2) if p95_elapsed is not None else None
        ),
        "avg_sleep_seconds": avg_sleep,
        "overrun_count": overrun_count,
        "overrun_rate": (
            round(overrun_count / samples, 4) if samples else None
        ),
        "missed_boundary_count": missed_boundary_total,
        "missed_boundary_rate": missed_boundary_rate,
        "ingest_since_source_counts": ingest_source_metrics["source_counts"],
        "rebootstrap_cycles": ingest_source_metrics["rebootstrap_cycles"],
        "rebootstrap_events": ingest_source_metrics["rebootstrap_events"],
        "underfill_guard_retrigger_cycles": ingest_source_metrics[
            "underfill_guard_retrigger_cycles"
        ],
        "underfill_guard_retrigger_events": ingest_source_metrics[
            "underfill_guard_retrigger_events"
        ],
        "detection_gate_skip_counts": detection_skip_counts,
        "detection_gate_skip_events": sum(detection_skip_counts.values()),
        "detection_gate_run_counts": detection_run_counts,
        "detection_gate_run_events": sum(detection_run_counts.values()),
    }

    payload = {
        "version": 1,
        "updated_at": datetime.now(timezone.utc).strftime(
            "%Y-%m-%dT%H:%M:%SZ"
        ),
        "target_cycle_seconds": target_cycle_seconds,
        "window_size": effective_window,
        "boundary_tracking": {
            "mode": resolved_boundary_mode,
            "missed_boundary_supported": (
                resolved_boundary_mode == "boundary_scheduler"
            ),
        },
        "summary": summary,
        "recent_cycles": entries,
    }
    atomic_write_json(path, payload, indent=2)
    return summary


def upsert_prediction_health(
    symbol: str,
    timeframe: str,
    *,
    prediction_ok: bool,
    error: str | None = None,
    path: Path = PREDICTION_HEALTH_FILE,
) -> tuple[dict, bool, bool]:
    """
    prediction 성공/실패 결과를 health 파일에 반영한다.

    반환값:
    - entry: 반영된 최신 상태 엔트리
    - previous_degraded: 반영 이전 degraded 여부
    - current_degraded: 반영 이후 degraded 여부
    """
    entries = _load_prediction_health(path=path)
    key = _prediction_health_key(symbol, timeframe)
    existing = entries.get(key, {})
    previous_degraded = bool(existing.get("degraded", False))
    now_utc = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    if prediction_ok:
        entry = {
            "symbol": symbol,
            "timeframe": timeframe,
            "degraded": False,
            "last_success_at": now_utc,
            "last_failure_at": existing.get("last_failure_at"),
            "last_error": None,
            "consecutive_failures": 0,
            "updated_at": now_utc,
        }
    else:
        raw_failures = existing.get("consecutive_failures", 0)
        try:
            previous_failures = int(raw_failures)
        except (TypeError, ValueError):
            previous_failures = 0
        entry = {
            "symbol": symbol,
            "timeframe": timeframe,
            "degraded": True,
            "last_success_at": existing.get("last_success_at"),
            "last_failure_at": now_utc,
            "last_error": error or "prediction_failed",
            "consecutive_failures": previous_failures + 1,
            "updated_at": now_utc,
        }

    entries[key] = entry
    _save_prediction_health(entries, path=path)
    return entry, previous_degraded, bool(entry["degraded"])


def _lookback_days_for_timeframe(timeframe: str) -> int:
    """
    timeframe별 기본 조회/초기 백필 범위를 반환한다.
    - 1m: retention 기본값(14d)
    - 기타: 기존 LOOKBACK_DAYS(30d)
    """
    if timeframe == "1m":
        return RETENTION_1M_DEFAULT_DAYS
    return LOOKBACK_DAYS


def get_disk_usage_percent(path: Path = DISK_USAGE_PATH) -> float:
    usage = shutil.disk_usage(path)
    if usage.total <= 0:
        return 0.0
    return round((usage.used / usage.total) * 100, 2)


def resolve_disk_watermark_level(
    usage_percent: float,
    *,
    warn_percent: int = DISK_WATERMARK_WARN_PERCENT,
    critical_percent: int = DISK_WATERMARK_CRITICAL_PERCENT,
    block_percent: int = DISK_WATERMARK_BLOCK_PERCENT,
) -> str:
    if usage_percent >= block_percent:
        return "block"
    if usage_percent >= critical_percent:
        return "critical"
    if usage_percent >= warn_percent:
        return "warn"
    return "normal"


def should_enforce_1m_retention(
    last_enforced_at: datetime | None,
    now: datetime,
    *,
    interval_seconds: int = RETENTION_ENFORCE_INTERVAL_SECONDS,
) -> bool:
    if last_enforced_at is None:
        return True
    return (now - last_enforced_at).total_seconds() >= interval_seconds


def should_block_initial_backfill(
    *,
    disk_level: str,
    timeframe: str,
    state_since: datetime | None,
    last_time: datetime | None,
) -> bool:
    return (
        disk_level == "block"
        and timeframe == "1m"
        and state_since is None
        and last_time is None
    )


def resolve_ingest_since(
    *,
    symbol: str,
    timeframe: str,
    state_since: datetime | None,
    last_time: datetime | None,
    disk_level: str,
    force_rebootstrap: bool = False,
    bootstrap_since: datetime | None = None,
    enforce_full_backfill: bool = False,
    now: datetime | None = None,
) -> tuple[datetime | None, str]:
    """
    ingest 시작 시점을 결정한다.

    우선순위:
    1) DB last timestamp (SoT)
    2) lookback bootstrap

    state cursor가 존재해도 DB에서 last timestamp를 찾지 못하면 drift로 보고
    lookback bootstrap을 다시 수행한다.
    """
    resolved_now = now or datetime.now(timezone.utc)
    if (
        enforce_full_backfill
        and timeframe == DOWNSAMPLE_SOURCE_TIMEFRAME
        and bootstrap_since is not None
    ):
        return bootstrap_since, "full_backfill_exchange_earliest"

    if force_rebootstrap:
        if should_block_initial_backfill(
            disk_level=disk_level,
            timeframe=timeframe,
            state_since=None,
            last_time=None,
        ):
            return None, "blocked_storage_guard"

        lookback_days = _lookback_days_for_timeframe(timeframe)
        return (
            resolved_now - timedelta(days=lookback_days),
            "underfilled_rebootstrap",
        )

    if last_time is not None:
        if state_since is not None and state_since > last_time:
            logger.warning(
                f"[{symbol} {timeframe}] ingest cursor drift detected: "
                f"state_since={state_since.strftime('%Y-%m-%dT%H:%M:%SZ')} "
                f"> db_last={last_time.strftime('%Y-%m-%dT%H:%M:%SZ')}. "
                "Using db_last as source of truth."
            )
        return last_time, "db_last"

    # DB에 데이터가 없는데 state cursor가 남아 있는 경우(드리프트)는
    # 초기 백필과 동일하게 취급해 lookback bootstrap을 재수행한다.
    guard_state_since = state_since
    source = "bootstrap_lookback"
    if state_since is not None:
        guard_state_since = None
        source = "state_drift_rebootstrap"
        logger.warning(
            f"[{symbol} {timeframe}] state cursor exists but DB has no last timestamp. "
            "Rebootstrapping from lookback window."
        )

    if should_block_initial_backfill(
        disk_level=disk_level,
        timeframe=timeframe,
        state_since=guard_state_since,
        last_time=last_time,
    ):
        return None, "blocked_storage_guard"

    if timeframe == DOWNSAMPLE_SOURCE_TIMEFRAME and bootstrap_since is not None:
        if source == "state_drift_rebootstrap":
            return (
                bootstrap_since,
                "state_drift_rebootstrap_exchange_earliest",
            )
        return bootstrap_since, "bootstrap_exchange_earliest"

    lookback_days = _lookback_days_for_timeframe(timeframe)
    return resolved_now - timedelta(days=lookback_days), source


def _minimum_required_lookback_rows(
    timeframe: str, lookback_days: int
) -> int | None:
    # 현재 운영 기준에서 coverage 보정은 1h canonical에만 적용한다.
    if timeframe != "1h":
        return None
    expected = lookback_days * 24
    if expected <= 0:
        return None
    return max(1, int(expected * LOOKBACK_MIN_ROWS_RATIO))


def get_lookback_close_count(
    query_api, symbol: str, timeframe: str, lookback_days: int
) -> int | None:
    query = f"""
    from(bucket: "{INFLUXDB_BUCKET}")
      |> range(start: -{lookback_days}d)
      |> filter(fn: (r) => r["_measurement"] == "ohlcv")
      |> filter(fn: (r) => r["symbol"] == "{symbol}")
      |> filter(fn: (r) => r["timeframe"] == "{timeframe}")
      |> filter(fn: (r) => r["_field"] == "close")
      |> count(column: "_value")
    """
    try:
        result = query_api.query(query=query)
    except Exception as e:
        logger.error(f"[{symbol} {timeframe}] lookback count query failed: {e}")
        return None

    if not result:
        return 0

    for table in result:
        if not table.records:
            continue
        value = table.records[0].get_value()
        try:
            return int(value)
        except (TypeError, ValueError):
            return None
    return 0


def enforce_1m_retention(
    delete_api,
    symbols: list[str],
    *,
    now: datetime | None = None,
    retention_days: int = RETENTION_1M_DEFAULT_DAYS,
) -> None:
    """
    1m 원본 데이터의 보존 범위를 강제한다.
    - 정책 범위 밖 값은 [14, 30]으로 clamp.
    - measurement=ohlcv, timeframe=1m만 대상으로 삭제한다.
    """
    resolved_now = now or datetime.now(timezone.utc)
    effective_days = max(
        RETENTION_1M_DEFAULT_DAYS,
        min(retention_days, RETENTION_1M_MAX_DAYS),
    )
    cutoff = (resolved_now - timedelta(days=effective_days)).replace(
        microsecond=0
    )
    epoch = datetime(1970, 1, 1, tzinfo=timezone.utc)

    for symbol in symbols:
        predicate = (
            f'_measurement="ohlcv" AND symbol="{symbol}" AND timeframe="1m"'
        )
        delete_api.delete(
            start=epoch,
            stop=cutoff,
            predicate=predicate,
            bucket=INFLUXDB_BUCKET,
            org=INFLUXDB_ORG,
        )

    logger.info(
        f"[Retention] 1m retention enforced: days={effective_days}, "
        f"cutoff={cutoff.strftime('%Y-%m-%dT%H:%M:%SZ')}, symbols={len(symbols)}"
    )


def _load_downsample_lineage(
    path: Path | None = None,
) -> dict[str, dict]:
    resolved_path = path or DOWNSAMPLE_LINEAGE_FILE
    if not resolved_path.exists():
        return {}

    try:
        with open(resolved_path, "r") as f:
            payload = json.load(f)
    except (OSError, json.JSONDecodeError) as e:
        logger.error(f"Failed to load downsample lineage file: {e}")
        return {}

    entries = payload.get("entries")
    if not isinstance(entries, dict):
        logger.error(
            "Invalid downsample lineage format: entries is not a dict."
        )
        return {}
    return entries


def _save_downsample_lineage(
    entries: dict[str, dict],
    path: Path | None = None,
) -> None:
    resolved_path = path or DOWNSAMPLE_LINEAGE_FILE
    payload = {
        "version": 1,
        "updated_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "entries": entries,
    }
    atomic_write_json(resolved_path, payload, indent=2)


def upsert_downsample_lineage(
    *,
    symbol: str,
    target_timeframe: str,
    source_timeframe: str,
    source_rows: int,
    total_buckets: int,
    complete_buckets: int,
    incomplete_buckets: int,
    last_bucket_open: datetime | None,
    status: str,
    path: Path | None = None,
) -> None:
    entries = _load_downsample_lineage(path=path)
    key = _prediction_health_key(symbol, target_timeframe)
    now_utc = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    entries[key] = {
        "symbol": symbol,
        "timeframe": target_timeframe,
        "source_timeframe": source_timeframe,
        "source_rows": source_rows,
        "total_buckets": total_buckets,
        "complete_buckets": complete_buckets,
        "incomplete_buckets": incomplete_buckets,
        "last_bucket_open": (
            last_bucket_open.strftime("%Y-%m-%dT%H:%M:%SZ")
            if last_bucket_open is not None
            else None
        ),
        "status": status,
        "updated_at": now_utc,
    }
    _save_downsample_lineage(entries, path=path)


def _query_ohlcv_frame(
    query_api,
    *,
    symbol: str,
    timeframe: str,
    lookback_days: int,
) -> pd.DataFrame:
    query = f"""
    from(bucket: "{INFLUXDB_BUCKET}")
      |> range(start: -{lookback_days}d)
      |> filter(fn: (r) => r["_measurement"] == "ohlcv")
      |> filter(fn: (r) => r["symbol"] == "{symbol}")
      |> filter(fn: (r) => r["timeframe"] == "{timeframe}")
      |> pivot(rowKey:["_time"], columnKey: ["_field"], valueColumn: "_value")
      |> sort(columns: ["_time"], desc: false)
    """
    result = query_api.query_data_frame(query)
    if isinstance(result, list):
        frames = [
            frame
            for frame in result
            if isinstance(frame, pd.DataFrame) and not frame.empty
        ]
        if not frames:
            return pd.DataFrame()
        df = pd.concat(frames, ignore_index=True)
    else:
        df = result

    if not isinstance(df, pd.DataFrame) or df.empty:
        return pd.DataFrame()

    required = {"_time", "open", "high", "low", "close", "volume"}
    if not required.issubset(df.columns):
        missing = sorted(required - set(df.columns))
        logger.error(
            f"[{symbol} {timeframe}] Downsample source columns missing: {missing}"
        )
        return pd.DataFrame()

    source = df[list(required)].copy()
    source.rename(columns={"_time": "timestamp"}, inplace=True)
    source["timestamp"] = pd.to_datetime(source["timestamp"], utc=True)
    source.drop_duplicates(subset=["timestamp"], keep="last", inplace=True)
    source.sort_values(by="timestamp", inplace=True)
    source.set_index("timestamp", inplace=True)
    return source[["open", "high", "low", "close", "volume"]]


def _downsample_rule(timeframe: str) -> str:
    if timeframe == "1d":
        return "1D"
    if timeframe == "1w":
        return "1W-MON"
    if timeframe == "1M":
        return "1MS"
    raise ValueError(f"Unsupported downsample target timeframe: {timeframe}")


def _expected_source_count(bucket_open: datetime, target_timeframe: str) -> int:
    next_boundary = next_timeframe_boundary(bucket_open, target_timeframe)
    step_seconds = int((next_boundary - bucket_open).total_seconds())
    if step_seconds <= 0:
        return 0
    return step_seconds // 3600


def downsample_ohlcv_frame(
    source_df: pd.DataFrame,
    *,
    target_timeframe: str,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    if source_df.empty:
        return pd.DataFrame(), pd.DataFrame()

    grouped = source_df.resample(
        _downsample_rule(target_timeframe), label="left", closed="left"
    )
    aggregated = grouped.agg(
        {
            "open": "first",
            "high": "max",
            "low": "min",
            "close": "last",
            "volume": "sum",
        }
    )
    counts = grouped["open"].count().rename("source_count")
    aggregated = aggregated.join(counts)
    aggregated.dropna(subset=["open", "high", "low", "close"], inplace=True)
    if aggregated.empty:
        return pd.DataFrame(), pd.DataFrame()

    expected = [
        _expected_source_count(
            bucket_open.to_pydatetime().astimezone(timezone.utc),
            target_timeframe,
        )
        for bucket_open in aggregated.index
    ]
    aggregated["expected_count"] = expected
    complete = aggregated[
        aggregated["source_count"] == aggregated["expected_count"]
    ].copy()
    incomplete = aggregated[
        aggregated["source_count"] != aggregated["expected_count"]
    ].copy()

    return (
        complete[["open", "high", "low", "close", "volume"]],
        incomplete[
            [
                "open",
                "high",
                "low",
                "close",
                "volume",
                "source_count",
                "expected_count",
            ]
        ],
    )


def run_downsample_and_save(
    write_api,
    query_api,
    *,
    symbol: str,
    target_timeframe: str,
) -> tuple[datetime | None, str]:
    if target_timeframe not in DOWNSAMPLE_TARGET_TIMEFRAMES:
        return None, "unsupported"

    source_df = _query_ohlcv_frame(
        query_api,
        symbol=symbol,
        timeframe=DOWNSAMPLE_SOURCE_TIMEFRAME,
        lookback_days=DOWNSAMPLE_SOURCE_LOOKBACK_DAYS,
    )
    if source_df.empty:
        upsert_downsample_lineage(
            symbol=symbol,
            target_timeframe=target_timeframe,
            source_timeframe=DOWNSAMPLE_SOURCE_TIMEFRAME,
            source_rows=0,
            total_buckets=0,
            complete_buckets=0,
            incomplete_buckets=0,
            last_bucket_open=None,
            status="no_source_data",
        )
        return None, "no_data"

    complete_df, incomplete_df = downsample_ohlcv_frame(
        source_df, target_timeframe=target_timeframe
    )
    last_bucket_open = (
        complete_df.index[-1].to_pydatetime().astimezone(timezone.utc)
        if not complete_df.empty
        else None
    )

    upsert_downsample_lineage(
        symbol=symbol,
        target_timeframe=target_timeframe,
        source_timeframe=DOWNSAMPLE_SOURCE_TIMEFRAME,
        source_rows=len(source_df),
        total_buckets=len(complete_df) + len(incomplete_df),
        complete_buckets=len(complete_df),
        incomplete_buckets=len(incomplete_df),
        last_bucket_open=last_bucket_open,
        status="ok" if not complete_df.empty else "incomplete_only",
    )

    if not incomplete_df.empty:
        logger.warning(
            f"[{symbol} {target_timeframe}] Downsample incomplete buckets: {len(incomplete_df)}"
        )

    if complete_df.empty:
        return None, "no_data"

    export_df = complete_df.copy()
    export_df["symbol"] = symbol
    export_df["timeframe"] = target_timeframe
    write_api.write(
        bucket=INFLUXDB_BUCKET,
        org=INFLUXDB_ORG,
        record=export_df,
        data_frame_measurement_name="ohlcv",
        data_frame_tag_columns=["symbol", "timeframe"],
    )
    logger.info(
        f"[{symbol} {target_timeframe}] Downsample saved "
        f"(source_rows={len(source_df)}, complete={len(complete_df)}, incomplete={len(incomplete_df)})"
    )
    return last_bucket_open, "saved"


def _static_export_candidates(
    kind: str,
    symbol: str,
    timeframe: str,
    static_dir: Path | None = None,
) -> list[Path]:
    canonical, legacy = _static_export_paths(
        kind, symbol, timeframe, static_dir=static_dir
    )
    candidates = [canonical]
    if legacy is not None:
        candidates.append(legacy)
    return candidates


def _extract_updated_at_from_files(
    candidates: list[Path],
) -> tuple[str | None, str | None]:
    for path in candidates:
        if not path.exists():
            continue

        try:
            with open(path, "r") as f:
                payload = json.load(f)
        except (OSError, json.JSONDecodeError) as e:
            logger.error(f"Failed to read static export file {path.name}: {e}")
            return None, path.name

        updated_at = payload.get("updated_at")
        if isinstance(updated_at, str) and updated_at:
            return updated_at, path.name

        logger.warning(f"Invalid updated_at in static export file: {path.name}")
        return None, path.name

    return None, None


def build_runtime_manifest(
    symbols: list[str],
    timeframes: list[str],
    *,
    now: datetime | None = None,
    static_dir: Path | None = None,
    prediction_health_path: Path | None = None,
    symbol_activation_entries: dict[str, dict] | None = None,
) -> dict:
    """
    심볼/타임프레임별 정적 산출물 상태(manifest) 페이로드를 생성한다.
    """
    resolved_now = now or datetime.now(timezone.utc)
    generated_at = resolved_now.strftime("%Y-%m-%dT%H:%M:%SZ")
    resolved_static_dir = static_dir or STATIC_DIR
    resolved_prediction_health_path = (
        prediction_health_path or PREDICTION_HEALTH_FILE
    )
    health_entries = _load_prediction_health(
        path=resolved_prediction_health_path
    )

    entries: list[dict] = []
    status_counts: dict[str, int] = {}
    degraded_count = 0
    activation_entries = symbol_activation_entries or {}
    symbol_state_counts: dict[str, int] = {}
    visible_symbols: set[str] = set()

    for symbol in symbols:
        activation = activation_entries.get(symbol, {})
        visibility = (
            "visible"
            if activation.get("visibility") != "hidden_backfilling"
            else "hidden_backfilling"
        )
        symbol_state = activation.get("state", "ready_for_serving")
        is_full_backfilled = bool(
            activation.get("is_full_backfilled", visibility == "visible")
        )
        if visibility == "visible":
            visible_symbols.add(symbol)
        symbol_state_counts[symbol_state] = (
            symbol_state_counts.get(symbol_state, 0) + 1
        )

        for timeframe in timeframes:
            history_updated_at, history_file = _extract_updated_at_from_files(
                _static_export_candidates(
                    "history", symbol, timeframe, static_dir=resolved_static_dir
                )
            )
            snapshot = evaluate_prediction_status(
                symbol=symbol,
                timeframe=timeframe,
                now=resolved_now,
                static_dir=resolved_static_dir,
            )
            health = health_entries.get(
                _prediction_health_key(symbol, timeframe), {}
            )
            degraded = bool(health.get("degraded", False))
            raw_failures = health.get("consecutive_failures", 0)
            try:
                failure_count = int(raw_failures)
            except (TypeError, ValueError):
                failure_count = 0
            if degraded:
                degraded_count += 1

            status_counts[snapshot.status] = (
                status_counts.get(snapshot.status, 0) + 1
            )
            entries.append(
                {
                    "key": _prediction_health_key(symbol, timeframe),
                    "symbol": symbol,
                    "timeframe": timeframe,
                    "history": {
                        "updated_at": history_updated_at,
                        "source_file": history_file,
                    },
                    "prediction": {
                        "status": snapshot.status,
                        "updated_at": snapshot.updated_at,
                        "age_minutes": snapshot.age_minutes,
                        "threshold_minutes": {
                            "soft": snapshot.soft_limit_minutes,
                            "hard": snapshot.hard_limit_minutes,
                        },
                        "source_detail": snapshot.detail,
                    },
                    "degraded": degraded,
                    "last_prediction_success_at": health.get("last_success_at"),
                    "last_prediction_failure_at": health.get("last_failure_at"),
                    "prediction_failure_count": failure_count,
                    "visibility": visibility,
                    "symbol_state": symbol_state,
                    "is_full_backfilled": is_full_backfilled,
                    "coverage_start_at": activation.get("coverage_start_at"),
                    "coverage_end_at": activation.get("coverage_end_at"),
                    "exchange_earliest_at": activation.get("exchange_earliest_at"),
                    "serve_allowed": (
                        visibility == "visible"
                        and snapshot.status in SERVE_ALLOWED_STATUSES
                    ),
                }
            )

    return {
        "version": 1,
        "generated_at": generated_at,
        "entries": entries,
        "summary": {
            "entry_count": len(entries),
            "status_counts": status_counts,
            "degraded_count": degraded_count,
            "visible_symbol_count": len(visible_symbols),
            "hidden_symbol_count": max(0, len(symbols) - len(visible_symbols)),
            "symbol_state_counts": symbol_state_counts,
        },
    }


def write_runtime_manifest(
    symbols: list[str],
    timeframes: list[str],
    *,
    now: datetime | None = None,
    static_dir: Path | None = None,
    prediction_health_path: Path | None = None,
    symbol_activation_entries: dict[str, dict] | None = None,
    path: Path | None = None,
) -> None:
    resolved_path = path or MANIFEST_FILE
    payload = build_runtime_manifest(
        symbols,
        timeframes,
        now=now,
        static_dir=static_dir,
        prediction_health_path=prediction_health_path,
        symbol_activation_entries=symbol_activation_entries,
    )
    atomic_write_json(resolved_path, payload, indent=2)
    logger.info(f"Runtime manifest updated: {resolved_path}")


def _query_last_timestamp(query_api, query: str) -> datetime | None:
    result = query_api.query(query=query)
    if len(result) == 0 or len(result[0].records) == 0:
        return None
    return result[0].records[0].get_time()


def _query_first_timestamp(query_api, query: str) -> datetime | None:
    result = query_api.query(query=query)
    if len(result) == 0 or len(result[0].records) == 0:
        return None
    return result[0].records[0].get_time()


def get_first_timestamp(
    query_api, symbol: str, timeframe: str
) -> datetime | None:
    query = f"""
    from(bucket: "{INFLUXDB_BUCKET}")
      |> range(start: 0)
      |> filter(fn: (r) => r["_measurement"] == "ohlcv")
      |> filter(fn: (r) => r["symbol"] == "{symbol}")
      |> filter(fn: (r) => r["timeframe"] == "{timeframe}")
      |> first(column: "_time")
    """
    legacy_query = f"""
    from(bucket: "{INFLUXDB_BUCKET}")
      |> range(start: 0)
      |> filter(fn: (r) => r["_measurement"] == "ohlcv")
      |> filter(fn: (r) => r["symbol"] == "{symbol}")
      |> filter(fn: (r) => not exists r["timeframe"])
      |> first(column: "_time")
    """

    try:
        first_time = _query_first_timestamp(query_api, query)
        if first_time is None and timeframe == PRIMARY_TIMEFRAME:
            first_time = _query_first_timestamp(query_api, legacy_query)
        return first_time
    except Exception as e:
        logger.error(
            f"[{symbol} {timeframe}] DB earliest 조회 중 에러: {e}"
        )
        return None


def get_last_timestamp(
    query_api, symbol, timeframe, *, full_range: bool = False
):
    """
    InfluxDB에서 해당 코인/타임프레임의 가장 마지막 데이터 시간(Timestamp)을 조회
    """
    lookback_days = _lookback_days_for_timeframe(timeframe)
    range_start = "0" if full_range else f"-{lookback_days}d"
    query = f"""
    from(bucket: "{INFLUXDB_BUCKET}")
      |> range(start: {range_start})
      |> filter(fn: (r) => r["_measurement"] == "ohlcv")
      |> filter(fn: (r) => r["symbol"] == "{symbol}")
      |> filter(fn: (r) => r["timeframe"] == "{timeframe}")
      |> last(column: "_time")
    """
    legacy_query = f"""
    from(bucket: "{INFLUXDB_BUCKET}")
      |> range(start: {range_start})
      |> filter(fn: (r) => r["_measurement"] == "ohlcv")
      |> filter(fn: (r) => r["symbol"] == "{symbol}")
      |> filter(fn: (r) => not exists r["timeframe"])
      |> last(column: "_time")
    """

    try:
        last_time = _query_last_timestamp(query_api, query)
        # B-003 전환 직후(legacy row만 존재)에도 과도한 초기 백필을 피하기 위한 fallback.
        if last_time is None and timeframe == PRIMARY_TIMEFRAME:
            last_time = _query_last_timestamp(query_api, legacy_query)
        if last_time is not None:
            # InfluxDB 시간은 UTC timezone이 포함됨.
            return last_time
    except Exception as e:
        logger.error(
            f"[{symbol} {timeframe}] DB 조회 중 에러 (아마 데이터 없음): {e}"
        )

    return None


def get_exchange_earliest_closed_timestamp(
    exchange,
    symbol: str,
    timeframe: str,
    *,
    now: datetime | None = None,
) -> datetime | None:
    try:
        rows = exchange.fetch_ohlcv(symbol, timeframe, since=0, limit=1)
    except Exception as e:
        logger.warning(
            f"[{symbol} {timeframe}] failed to fetch exchange earliest candle: {e}"
        )
        return None

    if not rows:
        return None

    try:
        first_open = datetime.fromtimestamp(
            int(rows[0][0]) / 1000, tz=timezone.utc
        )
    except (TypeError, ValueError):
        return None

    resolved_now = now or datetime.now(timezone.utc)
    last_closed = last_closed_candle_open(resolved_now, timeframe)
    if first_open > last_closed:
        return None
    return first_open


def get_exchange_latest_closed_timestamp(
    exchange,
    symbol: str,
    timeframe: str,
    *,
    now: datetime | None = None,
) -> datetime | None:
    resolved_now = now or datetime.now(timezone.utc)
    expected_latest_closed = last_closed_candle_open(resolved_now, timeframe)
    try:
        rows = exchange.fetch_ohlcv(symbol, timeframe, limit=3)
    except Exception as e:
        logger.warning(
            f"[{symbol} {timeframe}] failed to fetch exchange latest candle: {e}"
        )
        return None

    latest_closed: datetime | None = None
    for row in rows:
        try:
            open_at = datetime.fromtimestamp(int(row[0]) / 1000, tz=timezone.utc)
        except (TypeError, ValueError, IndexError):
            continue

        if open_at > expected_latest_closed:
            continue
        if latest_closed is None or open_at > latest_closed:
            latest_closed = open_at

    return latest_closed


def evaluate_detection_gate(
    query_api,
    detection_exchange,
    *,
    symbol: str,
    timeframe: str,
    now: datetime,
    last_saved: datetime | None = None,
) -> tuple[bool, str]:
    if timeframe in DOWNSAMPLE_TARGET_TIMEFRAMES:
        expected_latest_closed = last_closed_candle_open(now, timeframe)
        target_last = get_last_timestamp(
            query_api,
            symbol,
            timeframe,
            full_range=True,
        )
        if target_last is not None and target_last >= expected_latest_closed:
            return False, "already_materialized"
        return True, "materialization_due"

    latest_closed = get_exchange_latest_closed_timestamp(
        detection_exchange,
        symbol,
        timeframe,
        now=now,
    )
    if latest_closed is None:
        # 탐지 실패 시 skip 대신 실행 경로로 보수적으로 처리한다.
        return True, "detection_unavailable_fallback_run"

    reference_last = (
        last_saved
        if last_saved is not None
        else get_last_timestamp(query_api, symbol, timeframe)
    )
    if reference_last is not None and reference_last >= latest_closed:
        return False, "no_new_closed_candle"
    return True, "new_closed_candle"


def build_symbol_activation_entry(
    *,
    query_api,
    symbol: str,
    now: datetime,
    exchange_earliest: datetime | None,
    existing_entry: dict | None = None,
) -> dict:
    canonical_tf = DOWNSAMPLE_SOURCE_TIMEFRAME
    db_first = get_first_timestamp(query_api, symbol, canonical_tf)
    db_last = get_last_timestamp(
        query_api, symbol, canonical_tf, full_range=True
    )

    prev_entry = existing_entry if isinstance(existing_entry, dict) else {}
    prev_ready = bool(prev_entry.get("is_full_backfilled", False))
    tolerance = timedelta(hours=max(0, FULL_BACKFILL_TOLERANCE_HOURS))

    if prev_ready and db_first is not None:
        state = "ready_for_serving"
        visibility = "visible"
        is_full_backfilled = True
    elif db_first is None:
        state = "registered"
        visibility = "hidden_backfilling"
        is_full_backfilled = False
    elif exchange_earliest is None:
        state = "backfilling"
        visibility = "hidden_backfilling"
        is_full_backfilled = False
    else:
        starts_covered = db_first <= (exchange_earliest + tolerance)
        is_full_backfilled = starts_covered
        if starts_covered:
            state = "ready_for_serving"
            visibility = "visible"
        else:
            state = "backfilling"
            visibility = "hidden_backfilling"

    ready_at = prev_entry.get("ready_at")
    if is_full_backfilled and not ready_at:
        ready_at = now.strftime("%Y-%m-%dT%H:%M:%SZ")

    return {
        "symbol": symbol,
        "state": state,
        "visibility": visibility,
        "is_full_backfilled": is_full_backfilled,
        "coverage_start_at": _format_utc(db_first),
        "coverage_end_at": _format_utc(db_last),
        "exchange_earliest_at": _format_utc(exchange_earliest),
        "ready_at": ready_at,
        "updated_at": now.strftime("%Y-%m-%dT%H:%M:%SZ"),
    }


def save_history_to_json(df, symbol, timeframe):
    """
    과거 데이터 정적 파일 생성.
    """
    try:
        export_df = df.copy()
        export_df["timestamp"] = export_df.index.strftime(
            "%Y-%m-%dT%H:%M:%SZ"
        )  # UTC Aware 가정

        json_output = {
            "symbol": symbol,
            "data": export_df[
                ["timestamp", "open", "high", "low", "close", "volume"]
            ].to_dict(orient="records"),
            "updated_at": datetime.now(timezone.utc).strftime(
                "%Y-%m-%dT%H:%M:%SZ"
            ),
            "timeframe": timeframe,
            "type": f"history_{timeframe}",
        }

        canonical_path, legacy_path = _static_export_paths(
            "history", symbol, timeframe
        )
        atomic_write_json(canonical_path, json_output)
        if legacy_path is not None:
            atomic_write_json(legacy_path, json_output)

        logger.info(
            f"[{symbol} {timeframe}] 정적 파일 생성 완료: "
            f"canonical={canonical_path}, legacy={legacy_path}"
        )
    except Exception as e:
        logger.error(f"[{symbol} {timeframe}] 정적 파일 생성 실패: {e}")


def fetch_and_save(
    write_api, symbol, since_ts, timeframe
) -> tuple[datetime | None, str]:
    """
    ccxt로 데이터 가져와서 InfluxDB에 저장
    """
    exchange = ccxt.binance()
    exchange.enableRateLimit = True

    # since_ts가 datetime 객체라면 밀리초(int)로 변환 필요
    if isinstance(since_ts, datetime):
        since_ms = int(since_ts.timestamp() * 1000)
    else:
        since_ms = int(since_ts)  # 이미 int면 그대로

    try:
        now = datetime.now(timezone.utc)
        now_ms = int(now.timestamp() * 1000)
        last_closed_open = last_closed_candle_open(now, timeframe)
        last_closed_ms = int(last_closed_open.timestamp() * 1000)

        df, page_count = _fetch_ohlcv_paginated(
            exchange=exchange,
            symbol=symbol,
            timeframe=timeframe,
            since_ms=since_ms,
            until_ms=now_ms,
        )
        if df.empty:
            logger.info(f"[{symbol} {timeframe}] 새로운 데이터 없음.")
            return None, "no_data"

        # 미완료 캔들은 저장하지 않는다.
        before_filter = len(df)
        df = df[df["timestamp"] <= last_closed_ms]
        dropped = before_filter - len(df)
        if dropped > 0:
            logger.info(
                f"[{symbol} {timeframe}] 미완료 캔들 {dropped}개 제외 "
                f"(last_closed_open={last_closed_open.strftime('%Y-%m-%dT%H:%M:%SZ')})"
            )
        if df.empty:
            logger.info(
                f"[{symbol} {timeframe}] 저장 가능한 closed candle 없음 "
                f"(last_closed_open={last_closed_open.strftime('%Y-%m-%dT%H:%M:%SZ')})."
            )
            return None, "no_data"

        gaps = _detect_gaps_from_ms_timestamps(
            timestamps_ms=df["timestamp"].tolist(), timeframe=timeframe
        )
        if gaps:
            total_missing = sum(gap.missing_count for gap in gaps)
            first_gap = gaps[0]
            logger.warning(
                f"[{symbol} {timeframe}] Gap 감지: windows={len(gaps)}, missing={total_missing}, "
                f"first={first_gap.start_open.strftime('%Y-%m-%dT%H:%M:%SZ')}~"
                f"{first_gap.end_open.strftime('%Y-%m-%dT%H:%M:%SZ')}"
            )
            df, refill_pages = _refill_detected_gaps(
                exchange=exchange,
                symbol=symbol,
                timeframe=timeframe,
                source_df=df,
                gaps=gaps,
                last_closed_ms=last_closed_ms,
            )
            if refill_pages > 0:
                logger.info(
                    f"[{symbol} {timeframe}] Gap refill 시도 완료 (pages={refill_pages})"
                )

            remaining_gaps = _detect_gaps_from_ms_timestamps(
                timestamps_ms=df["timestamp"].tolist(),
                timeframe=timeframe,
            )
            if remaining_gaps:
                remaining_missing = sum(
                    gap.missing_count for gap in remaining_gaps
                )
                logger.warning(
                    f"[{symbol} {timeframe}] Gap 잔존: windows={len(remaining_gaps)}, missing={remaining_missing}"
                )
            else:
                logger.info(f"[{symbol} {timeframe}] Gap refill 완료.")

        df["timestamp"] = pd.to_datetime(
            df["timestamp"], unit="ms"
        ).dt.tz_localize("UTC")
        df.set_index("timestamp", inplace=True)

        # 태그 추가
        df["symbol"] = symbol
        df["timeframe"] = timeframe

        # 저장
        write_api.write(
            bucket=INFLUXDB_BUCKET,
            org=INFLUXDB_ORG,
            record=df,
            data_frame_measurement_name="ohlcv",
            data_frame_tag_columns=["symbol", "timeframe"],
        )
        logger.info(
            f"[{symbol} {timeframe}] {len(df)}개 봉 저장 완료 (pages={page_count}, Last={df.index[-1]})"
        )
        latest_saved_at = df.index[-1].to_pydatetime().astimezone(timezone.utc)

        # TODO: SSG 파일 생성을 DB 조회 후 덮어쓰기로 구현?
        return latest_saved_at, "saved"

    except Exception as e:
        logger.error(f"[{symbol} {timeframe}] 수집 실패: {e}")
        return None, "failed"


def _fetch_ohlcv_paginated(
    exchange, symbol: str, timeframe: str, since_ms: int, until_ms: int
) -> tuple[pd.DataFrame, int]:
    fetch_limit = 1000
    timeframe_ms = exchange.parse_timeframe(timeframe) * 1000
    cursor = int(since_ms)
    page_count = 0
    chunks: list[pd.DataFrame] = []

    while cursor <= until_ms:
        ohlcv = exchange.fetch_ohlcv(
            symbol, timeframe, since=cursor, limit=fetch_limit
        )
        if not ohlcv:
            break

        page_count += 1
        chunk = pd.DataFrame(
            ohlcv,
            columns=[
                "timestamp",
                "open",
                "high",
                "low",
                "close",
                "volume",
            ],
        )
        chunk = chunk[chunk["timestamp"] <= until_ms]
        if chunk.empty:
            break
        chunks.append(chunk)

        last_ts = int(chunk.iloc[-1]["timestamp"])
        if last_ts < cursor:
            break

        next_cursor = last_ts + timeframe_ms
        if len(ohlcv) < fetch_limit or next_cursor <= cursor:
            break

        cursor = next_cursor

    if not chunks:
        empty_df = pd.DataFrame(
            columns=["timestamp", "open", "high", "low", "close", "volume"]
        )
        return empty_df, page_count

    merged = pd.concat(chunks, ignore_index=True)
    merged.drop_duplicates(subset=["timestamp"], keep="last", inplace=True)
    merged.sort_values(by="timestamp", inplace=True)
    return merged, page_count


def _detect_gaps_from_ms_timestamps(timestamps_ms: list[int], timeframe: str):
    candle_opens = [
        datetime.fromtimestamp(int(ts) / 1000, tz=timezone.utc)
        for ts in timestamps_ms
    ]
    return detect_timeframe_gaps(candle_opens, timeframe)


def _refill_detected_gaps(
    exchange,
    symbol: str,
    timeframe: str,
    source_df: pd.DataFrame,
    gaps,
    last_closed_ms: int,
) -> tuple[pd.DataFrame, int]:
    if not gaps:
        return source_df, 0

    refill_since_ms = int(gaps[0].start_open.timestamp() * 1000)
    refill_df, refill_pages = _fetch_ohlcv_paginated(
        exchange=exchange,
        symbol=symbol,
        timeframe=timeframe,
        since_ms=refill_since_ms,
        until_ms=last_closed_ms,
    )
    if refill_df.empty:
        return source_df, refill_pages

    merged = pd.concat([source_df, refill_df], ignore_index=True)
    merged.drop_duplicates(subset=["timestamp"], keep="last", inplace=True)
    merged.sort_values(by="timestamp", inplace=True)
    return merged, refill_pages


def run_prediction_and_save(
    write_api, symbol, timeframe
) -> tuple[str, str | None]:
    """모델 로드 -> 예측 -> 저장"""
    if not prediction_enabled_for_timeframe(timeframe):
        logger.info(
            f"[{symbol} {timeframe}] prediction disabled by policy. "
            "Skipping prediction artifact generation."
        )
        return "skipped", None

    safe_symbol = symbol.replace("/", "_")
    model_candidates = [
        MODELS_DIR / f"model_{safe_symbol}_{timeframe}.json",
        MODELS_DIR / f"model_{safe_symbol}.json",
    ]
    model_file = next(
        (candidate for candidate in model_candidates if candidate.exists()),
        None,
    )
    if model_file is None:
        logger.warning(f"[{symbol} {timeframe}] 모델 없음")
        return "failed", "model_missing"

    try:
        with open(model_file, "r") as fin:
            model = model_from_json(fin.read())

        # 예측 시작 시점을 "다음 캔들 경계"로 정렬한다.
        # 예: 10:37 + 1h -> 11:00 시작
        now = datetime.now(timezone.utc)
        prediction_start = next_timeframe_boundary(now, timeframe)
        prediction_freq = timeframe_to_pandas_freq(timeframe)
        future = pd.DataFrame(
            {
                "ds": pd.date_range(
                    start=prediction_start, periods=24, freq=prediction_freq
                )
            }
        )
        future["ds"] = future["ds"].dt.tz_localize(None)  # prophet은 tz-naive

        # As-Is: 여기서는 과거 데이터 없이 모델이 기억하는 패턴으로만 예측
        # To-Do: Training Worker 구축
        forecast = model.predict(future)

        # 필요한 데이터만 추출 (경계 기준으로 생성했으므로 head만 사용)
        next_forecast = forecast.head(24).copy()

        if next_forecast.empty:
            logger.warning(f"[{symbol} {timeframe}] 예측 범위 생성 실패.")
            return "failed", "empty_forecast"

        # 저장 (SSG)
        export_data = next_forecast[["ds", "yhat", "yhat_lower", "yhat_upper"]]
        export_data["ds"] = pd.to_datetime(export_data["ds"]).dt.strftime(
            "%Y-%m-%dT%H:%M:%SZ"
        )

        export_data.rename(
            columns={
                "ds": "timestamp",
                "yhat": "price",
                "yhat_lower": "lower_bound",
                "yhat_upper": "upper_bound",
            },
            inplace=True,
        )

        json_output = {
            "symbol": symbol,
            "timeframe": timeframe,
            "updated_at": now.strftime("%Y-%m-%dT%H:%M:%SZ"),  # 생성 시점 기록
            "forecast": export_data.to_dict(orient="records"),
        }

        # 파일 저장 (전환 기간: canonical + legacy 동시 유지)
        canonical_path, legacy_path = _static_export_paths(
            "prediction", symbol, timeframe
        )
        atomic_write_json(canonical_path, json_output, indent=2)
        if legacy_path is not None:
            atomic_write_json(legacy_path, json_output, indent=2)

        logger.info(
            f"[{symbol} {timeframe}] SSG 파일 생성 완료: canonical={canonical_path}, legacy={legacy_path} "
            f"(start={prediction_start.strftime('%Y-%m-%dT%H:%M:%SZ')}, freq={timeframe})"
        )

        # 저장(DB)
        next_forecast["ds"] = pd.to_datetime(
            next_forecast["ds"]
        ).dt.tz_localize(
            "UTC"
        )  # 불필요한 연산 같기는 한데,,, 방어용???
        next_forecast = next_forecast[
            ["ds", "yhat", "yhat_lower", "yhat_upper"]
        ]
        next_forecast.rename(columns={"ds": "timestamp"}, inplace=True)
        next_forecast.set_index(
            "timestamp", inplace=True
        )  # InfluxDB는 index가 timestamp
        next_forecast["symbol"] = symbol
        next_forecast["timeframe"] = timeframe

        write_api.write(
            bucket=INFLUXDB_BUCKET,
            org=INFLUXDB_ORG,
            record=next_forecast,
            data_frame_measurement_name="prediction",
            data_frame_tag_columns=["symbol", "timeframe"],
        )
        logger.info(
            f"[{symbol} {timeframe}] {len(next_forecast)}개 예측 저장 완료"
        )
        return "ok", None

    except Exception as e:
        logger.error(f"[{symbol} {timeframe}] 예측 에러: {e}")
        return "failed", f"prediction_error: {e}"


def update_full_history_file(query_api, symbol, timeframe):
    """DB에서 최근 30일치 데이터를 긁어와서 history json 파일 갱신"""
    lookback_days = _lookback_days_for_timeframe(timeframe)
    query = f"""
    from(bucket: "{INFLUXDB_BUCKET}")
      |> range(start: -{lookback_days}d)
      |> filter(fn: (r) => r["_measurement"] == "ohlcv")
      |> filter(fn: (r) => r["symbol"] == "{symbol}")
      |> filter(fn: (r) => r["timeframe"] == "{timeframe}")
      |> pivot(rowKey:["_time"], columnKey: ["_field"], valueColumn: "_value")
      |> sort(columns: ["_time"], desc: false)
    """
    try:
        df = query_api.query_data_frame(query)
        if not df.empty:
            df.rename(columns={"_time": "timestamp"}, inplace=True)  # UTC Aware
            df.set_index("timestamp", inplace=True)
            save_history_to_json(df, symbol, timeframe)
    except Exception as e:
        logger.error(f"[{symbol} {timeframe}] History 갱신 중 에러: {e}")


def run_worker():
    scheduler_mode = WORKER_SCHEDULER_MODE
    if scheduler_mode not in VALID_WORKER_SCHEDULER_MODES:
        logger.warning(
            "[Scheduler] unsupported WORKER_SCHEDULER_MODE=%s, fallback to poll_loop.",
            scheduler_mode,
        )
        scheduler_mode = "poll_loop"

    logger.info(
        f"[Pipeline Worker] Started. Target: {TARGET_COINS}, Timeframes: {TIMEFRAMES}, "
        f"SchedulerMode: {scheduler_mode}"
    )

    client = InfluxDBClient(
        url=INFLUXDB_URL, token=INFLUXDB_TOKEN, org=INFLUXDB_ORG
    )
    write_api = client.write_api(write_options=SYNCHRONOUS)
    query_api = client.query_api()
    delete_api = client.delete_api()
    ingest_state_store = IngestStateStore(INGEST_STATE_FILE)
    symbol_activation_entries = _load_symbol_activation()
    previous_disk_level: str | None = None
    last_retention_enforced_at: datetime | None = None
    activation_exchange = ccxt.binance()
    activation_exchange.enableRateLimit = True
    next_boundary_by_timeframe: dict[str, datetime] = {}
    if scheduler_mode == "boundary":
        next_boundary_by_timeframe = initialize_boundary_schedule(
            datetime.now(timezone.utc), TIMEFRAMES
        )

    send_alert("Worker Started.")

    while True:
        cycle_started_at = datetime.now(timezone.utc)
        start_time = time.time()
        cycle_since_source_counts: dict[str, int] = {}
        cycle_detection_skip_counts: dict[str, int] = {}
        cycle_detection_run_counts: dict[str, int] = {}
        cycle_missed_boundary_count: int | None = None
        try:
            logger.info(
                f"\n[Cycle] 작업 시작: {cycle_started_at.strftime('%Y-%m-%d %H:%M:%S')}"
            )
            cycle_now = cycle_started_at
            active_timeframes = TIMEFRAMES
            if scheduler_mode == "boundary":
                (
                    active_timeframes,
                    cycle_missed_boundary_count,
                    next_boundary_at,
                ) = resolve_boundary_due_timeframes(
                    now=cycle_now,
                    timeframes=TIMEFRAMES,
                    next_boundary_by_timeframe=next_boundary_by_timeframe,
                )
                if not active_timeframes:
                    sleep_until_boundary = (
                        (next_boundary_at - cycle_now).total_seconds()
                        if next_boundary_at is not None
                        else CYCLE_TARGET_SECONDS
                    )
                    sleep_time = max(1.0, sleep_until_boundary)
                    elapsed = time.time() - start_time
                    append_runtime_cycle_metrics(
                        started_at=cycle_started_at,
                        elapsed_seconds=elapsed,
                        sleep_seconds=sleep_time,
                        overrun=False,
                        cycle_result="idle",
                        ingest_since_source_counts=cycle_since_source_counts,
                        detection_gate_skip_counts=cycle_detection_skip_counts,
                        detection_gate_run_counts=cycle_detection_run_counts,
                        boundary_tracking_mode="boundary_scheduler",
                        missed_boundary_count=cycle_missed_boundary_count,
                    )
                    logger.info(
                        "[Scheduler] no due timeframe at boundary cycle. "
                        f"sleep={sleep_time:.2f}s until next boundary."
                    )
                    time.sleep(sleep_time)
                    continue

            disk_level = "normal"
            disk_usage_percent: float | None = None

            try:
                disk_usage_percent = get_disk_usage_percent()
                disk_level = resolve_disk_watermark_level(disk_usage_percent)
                if previous_disk_level != disk_level:
                    msg = (
                        "[Storage Guard] "
                        f"usage={disk_usage_percent:.2f}% level={disk_level} "
                        f"(warn={DISK_WATERMARK_WARN_PERCENT}%, "
                        f"critical={DISK_WATERMARK_CRITICAL_PERCENT}%, "
                        f"block={DISK_WATERMARK_BLOCK_PERCENT}%)"
                    )
                    if disk_level == "normal":
                        logger.info(msg)
                    else:
                        logger.warning(msg)
                        send_alert(msg)
                previous_disk_level = disk_level
            except OSError as e:
                logger.error(f"[Storage Guard] disk usage check failed: {e}")

            if "1m" in TIMEFRAMES and should_enforce_1m_retention(
                last_retention_enforced_at, cycle_now
            ):
                try:
                    enforce_1m_retention(
                        delete_api,
                        TARGET_COINS,
                        now=cycle_now,
                    )
                    last_retention_enforced_at = cycle_now
                except Exception as e:
                    logger.error(f"[Retention] enforcement failed: {e}")
                    send_alert(f"[Retention Error] {e}")

            for symbol in TARGET_COINS:
                exchange_earliest = get_exchange_earliest_closed_timestamp(
                    activation_exchange,
                    symbol,
                    DOWNSAMPLE_SOURCE_TIMEFRAME,
                    now=cycle_now,
                )
                symbol_activation = build_symbol_activation_entry(
                    query_api=query_api,
                    symbol=symbol,
                    now=cycle_now,
                    exchange_earliest=exchange_earliest,
                    existing_entry=symbol_activation_entries.get(symbol),
                )
                symbol_activation_entries[symbol] = symbol_activation
                if symbol_activation["visibility"] == "hidden_backfilling":
                    _remove_static_exports_for_symbol(
                        symbol, TIMEFRAMES, static_dir=STATIC_DIR
                    )

                for timeframe in active_timeframes:
                    state_since = ingest_state_store.get_last_closed(
                        symbol, timeframe
                    )
                    last_time = get_last_timestamp(query_api, symbol, timeframe)
                    if scheduler_mode == "boundary":
                        should_run, gate_reason = evaluate_detection_gate(
                            query_api,
                            activation_exchange,
                            symbol=symbol,
                            timeframe=timeframe,
                            now=cycle_now,
                            last_saved=last_time,
                        )
                        if not should_run:
                            cycle_detection_skip_counts[gate_reason] = (
                                cycle_detection_skip_counts.get(gate_reason, 0)
                                + 1
                            )
                            logger.info(
                                f"[{symbol} {timeframe}] detection gate skip "
                                f"(reason={gate_reason})"
                            )
                            continue
                        cycle_detection_run_counts[gate_reason] = (
                            cycle_detection_run_counts.get(gate_reason, 0) + 1
                        )

                    lookback_days = _lookback_days_for_timeframe(timeframe)
                    force_rebootstrap = False
                    min_required_rows = _minimum_required_lookback_rows(
                        timeframe, lookback_days
                    )
                    if min_required_rows is not None:
                        close_count = get_lookback_close_count(
                            query_api, symbol, timeframe, lookback_days
                        )
                        if (
                            close_count is not None
                            and close_count < min_required_rows
                        ):
                            force_rebootstrap = True
                            logger.warning(
                                f"[{symbol} {timeframe}] canonical coverage underfilled: "
                                f"close_count={close_count} < min_required={min_required_rows}. "
                                "Rebootstrapping from lookback."
                            )
                    since, since_source = resolve_ingest_since(
                        symbol=symbol,
                        timeframe=timeframe,
                        state_since=state_since,
                        last_time=last_time,
                        disk_level=disk_level,
                        force_rebootstrap=force_rebootstrap,
                        bootstrap_since=(
                            exchange_earliest
                            if timeframe == DOWNSAMPLE_SOURCE_TIMEFRAME
                            else None
                        ),
                        enforce_full_backfill=(
                            timeframe == DOWNSAMPLE_SOURCE_TIMEFRAME
                            and symbol_activation["visibility"]
                            == "hidden_backfilling"
                        ),
                        now=cycle_now,
                    )
                    cycle_since_source_counts[since_source] = (
                        cycle_since_source_counts.get(since_source, 0) + 1
                    )

                    if since_source == "blocked_storage_guard":
                        logger.warning(
                            f"[{symbol} {timeframe}] initial backfill blocked "
                            f"by storage guard (usage={disk_usage_percent}%)."
                        )
                        ingest_state_store.upsert(
                            symbol,
                            timeframe,
                            last_closed_ts=state_since,
                            status="blocked_storage_guard",
                        )
                        continue

                    if since_source in {
                        "bootstrap_lookback",
                        "bootstrap_exchange_earliest",
                        "full_backfill_exchange_earliest",
                        "state_drift_rebootstrap",
                        "state_drift_rebootstrap_exchange_earliest",
                    }:
                        if since_source.endswith("exchange_earliest"):
                            logger.info(
                                f"[{symbol} {timeframe}] 초기 데이터 수집 시작 "
                                f"(source={since_source}, since={_format_utc(since)})"
                            )
                        else:
                            lookback_days = _lookback_days_for_timeframe(timeframe)
                            logger.info(
                                f"[{symbol} {timeframe}] 초기 데이터 수집 시작 "
                                f"({lookback_days}일 전부터, source={since_source})"
                            )

                    # 수집
                    if timeframe in DOWNSAMPLE_TARGET_TIMEFRAMES:
                        latest_saved_at, ingest_result = (
                            run_downsample_and_save(
                                write_api,
                                query_api,
                                symbol=symbol,
                                target_timeframe=timeframe,
                            )
                        )
                    else:
                        latest_saved_at, ingest_result = fetch_and_save(
                            write_api, symbol, since, timeframe
                        )
                    if ingest_result == "saved":
                        ingest_state_store.upsert(
                            symbol,
                            timeframe,
                            last_closed_ts=latest_saved_at,
                            status="ok",
                        )
                    elif ingest_result == "failed":
                        ingest_state_store.upsert(
                            symbol,
                            timeframe,
                            last_closed_ts=state_since,
                            status="failed",
                        )

                    if (
                        timeframe == DOWNSAMPLE_SOURCE_TIMEFRAME
                        and symbol_activation["visibility"]
                        == "hidden_backfilling"
                    ):
                        symbol_activation = build_symbol_activation_entry(
                            query_api=query_api,
                            symbol=symbol,
                            now=cycle_now,
                            exchange_earliest=exchange_earliest,
                            existing_entry=symbol_activation_entries.get(
                                symbol
                            ),
                        )
                        symbol_activation_entries[symbol] = symbol_activation
                        if (
                            symbol_activation["visibility"]
                            == "hidden_backfilling"
                        ):
                            _remove_static_exports_for_symbol(
                                symbol, TIMEFRAMES, static_dir=STATIC_DIR
                            )

                    if symbol_activation["visibility"] == "hidden_backfilling":
                        logger.info(
                            f"[{symbol}] activation state={symbol_activation['state']} "
                            "-> skip static export/prediction for FE hide policy."
                        )
                        continue

                    # History 파일 갱신
                    update_full_history_file(query_api, symbol, timeframe)

                    # 예측
                    prediction_result, prediction_error = (
                        run_prediction_and_save(write_api, symbol, timeframe)
                    )
                    if prediction_result == "skipped":
                        continue

                    prediction_ok = prediction_result == "ok"
                    health, was_degraded, is_degraded = (
                        upsert_prediction_health(
                            symbol,
                            timeframe,
                            prediction_ok=prediction_ok,
                            error=prediction_error,
                        )
                    )
                    if is_degraded and not was_degraded:
                        logger.warning(
                            f"[{symbol} {timeframe}] prediction degraded: "
                            f"reason={health.get('last_error')}"
                        )
                        send_alert(
                            "[Predict Degraded] "
                            f"{symbol} {timeframe}\n"
                            f"reason={health.get('last_error')}\n"
                            f"last_success_at={health.get('last_success_at')}"
                        )
                    elif prediction_ok and was_degraded:
                        logger.info(
                            f"[{symbol} {timeframe}] prediction recovered."
                        )
                        send_alert(
                            "[Predict Recovery] "
                            f"{symbol} {timeframe}\n"
                            f"last_success_at={health.get('last_success_at')}"
                        )
                    elif is_degraded:
                        # degraded 유지 중에는 재알림 대신 누적 실패 횟수만 로그로 남긴다.
                        logger.info(
                            f"[{symbol} {timeframe}] prediction still degraded "
                            f"(consecutive_failures={health.get('consecutive_failures')})"
                        )

            try:
                _save_symbol_activation(symbol_activation_entries)
                write_runtime_manifest(
                    TARGET_COINS,
                    TIMEFRAMES,
                    symbol_activation_entries=symbol_activation_entries,
                )
            except Exception as e:
                logger.error(f"Runtime manifest update failed: {e}")
                send_alert(f"[Manifest Error] {e}")

            # Cycle Overrun 감지 및 주기 보정
            elapsed = time.time() - start_time
            sleep_time = CYCLE_TARGET_SECONDS - elapsed
            overrun = sleep_time <= 0

            try:
                append_runtime_cycle_metrics(
                    started_at=cycle_started_at,
                    elapsed_seconds=elapsed,
                    sleep_seconds=max(sleep_time, 0.0),
                    overrun=overrun,
                    cycle_result="ok",
                    ingest_since_source_counts=cycle_since_source_counts,
                    detection_gate_skip_counts=cycle_detection_skip_counts,
                    detection_gate_run_counts=cycle_detection_run_counts,
                    boundary_tracking_mode=(
                        "boundary_scheduler"
                        if scheduler_mode == "boundary"
                        else "poll_loop"
                    ),
                    missed_boundary_count=cycle_missed_boundary_count,
                )
            except Exception as e:
                logger.error(f"Runtime metrics update failed: {e}")

            if sleep_time > 0:
                logger.info(
                    f"Cycle finished in {elapsed:.2f}s. Sleeping for {sleep_time:.2f}s..."
                )
                time.sleep(sleep_time)
            else:
                warning_msg = (
                    f"[Warning] Cycle Overrun! Took {elapsed:.2f}s "
                    f"(Limit: {CYCLE_TARGET_SECONDS}s)"
                )
                send_alert(warning_msg)

        except Exception as e:
            # Worker가 죽지 않도록 잡지만, 운영자에게는 알림
            error_msg = f"Worker Critical Error:\n{traceback.format_exc()}"
            logger.error(error_msg)
            send_alert(error_msg)
            elapsed = time.time() - start_time
            try:
                append_runtime_cycle_metrics(
                    started_at=cycle_started_at,
                    elapsed_seconds=elapsed,
                    sleep_seconds=10.0,
                    overrun=elapsed > CYCLE_TARGET_SECONDS,
                    cycle_result="failed",
                    error=str(e),
                    ingest_since_source_counts=cycle_since_source_counts,
                    detection_gate_skip_counts=cycle_detection_skip_counts,
                    detection_gate_run_counts=cycle_detection_run_counts,
                    boundary_tracking_mode=(
                        "boundary_scheduler"
                        if scheduler_mode == "boundary"
                        else "poll_loop"
                    ),
                    missed_boundary_count=cycle_missed_boundary_count,
                )
            except Exception as metrics_error:
                logger.error(
                    f"Runtime metrics update failed after worker error: {metrics_error}"
                )
            time.sleep(10)  # 에러 루프 방지용 대기


if __name__ == "__main__":
    run_worker()
