"""
Pipeline worker orchestrator.

Why this file exists:
- Runtime orchestration(역할 선택, 스케줄, 알림, 상태 저장)을 한곳에서 제어한다.
- 실제 도메인 로직(ingest/predict/export)은 workers/*로 분리해 변경 폭을 줄인다.
- 래퍼 함수를 유지하는 이유는 테스트가 `scripts.pipeline_worker.*` 심볼을
  직접 monkeypatch하는 계약을 이미 사용하고 있기 때문이다.

즉, 이 파일은 "비즈니스 계산"보다 "운영 제어면(control-plane)"에 집중한다.
"""

import ccxt
import pandas as pd
from influxdb_client import InfluxDBClient
from influxdb_client.client.write_api import SYNCHRONOUS
import json
import os
import shutil
import sys
import time
import math
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
import requests
import traceback
from utils.logger import get_logger
from utils.config import INGEST_TIMEFRAMES, PRIMARY_TIMEFRAME, TARGET_SYMBOLS
from utils.file_io import atomic_write_json
from utils.ingest_state import IngestStateStore
from utils.pipeline_contracts import (
    DetectionGateDecision,
    IngestExecutionOutcome,
    IngestExecutionResult,
    IngestSinceSource,
    PredictionExecutionOutcome,
    PredictionExecutionResult,
    PublishGateDecision,
    PublishGateReason,
    StorageGuardLevel,
    SymbolActivationSnapshot,
    SymbolVisibility,
    WatermarkCursor,
    format_utc_datetime,
    is_rebootstrap_source,
    parse_ingest_execution_result,
    parse_ingest_since_source,
    parse_prediction_execution_result,
    parse_utc_datetime,
)
from utils.pipeline_runtime_state import SymbolActivationStore, WatermarkStore
from utils.prediction_status import evaluate_prediction_status
from utils.time_alignment import (
    detect_timeframe_gaps,
    last_closed_candle_open,
    next_timeframe_boundary,
    timeframe_to_pandas_freq,
)
from workers import export as export_ops
from workers import ingest as ingest_ops
from workers import predict as predict_ops

logger = get_logger(__name__)


def _ctx():
    """
    현재 모듈 객체를 workers/*에 전달하기 위한 컨텍스트 어댑터.

    Called from:
    - 거의 모든 wrapper 함수

    Why:
    - 구현은 workers/*로 이동했지만 테스트 monkeypatch 경로는
      `scripts.pipeline_worker.*`를 유지해야 해서 ctx 패턴을 사용한다.
    """
    # workers/* 함수에 모듈 컨텍스트를 넘겨 주입점을 단일화한다.
    # 이 패턴을 유지하면 테스트 monkeypatch 경로(scripts.pipeline_worker.*)를
    # 깨지 않고도 구현 본체를 workers/*로 이동할 수 있다.
    return sys.modules[__name__]


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
INGEST_WATERMARK_FILE = STATIC_DIR / "ingest_watermarks.json"
PREDICT_WATERMARK_FILE = STATIC_DIR / "predict_watermarks.json"
EXPORT_WATERMARK_FILE = STATIC_DIR / "export_watermarks.json"
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
WORKER_SCHEDULER_MODE = (
    os.getenv("WORKER_SCHEDULER_MODE", "boundary").strip().lower()
)
VALID_WORKER_SCHEDULER_MODES = {"poll_loop", "boundary"}
WORKER_EXECUTION_ROLE = (
    os.getenv("WORKER_EXECUTION_ROLE", "all").strip().lower()
)
VALID_WORKER_EXECUTION_ROLES = {"all", "ingest", "predict_export"}
WORKER_PUBLISH_MODE = (
    os.getenv("WORKER_PUBLISH_MODE", "predict_and_export").strip().lower()
)
VALID_WORKER_PUBLISH_MODES = {
    "predict_and_export",
    "predict_only",
    "export_only",
}


def resolve_worker_execution_role(raw_role: str) -> str:
    """
    Worker 실행 역할 결정
    VALID_WORKER_EXECUTION_ROLES = {"all", "ingest", "predict_export"}
    - all: ingest, predict, export 모두 실행
    - ingest: ingest만 실행
    - predict_export: predict, export만 실행

    Args:
      - raw_role: WORKER_EXECUTION_ROLE 환경 변수 값
    Returns:
      - str: 결정된 worker 실행 역할
    """
    if raw_role in VALID_WORKER_EXECUTION_ROLES:
        return raw_role
    logger.warning(
        "[Worker Role] unsupported WORKER_EXECUTION_ROLE=%s, fallback to all.",
        raw_role,
    )
    return "all"


def worker_role_runs_ingest(role: str) -> bool:
    """
    Worker 역할이 ingest를 실행하는지 확인한다.

    Args:
      - role: 결정된 worker 실행 역할
    Returns:
      - bool: ingest를 실행하는지 여부
    """
    return role in {"all", "ingest"}


def worker_role_runs_publish(role: str) -> bool:
    """
    Worker 역할이 publish를 실행하는지 확인한다.

    Args:
      - role: 결정된 worker 실행 역할
    Returns:
      - bool: publish를 실행하는지 여부
    """
    return role in {"all", "predict_export"}


def resolve_worker_publish_mode(raw_mode: str) -> str:
    """
    Publish 모드 결정
    VALID_WORKER_PUBLISH_MODES = {"predict_and_export", "predict_only", "export_only"}
    - predict_and_export: predict, export 모두 실행
    - predict_only: predict만 실행
    - export_only: export만 실행

    Args:
      - raw_mode: WORKER_PUBLISH_MODE 환경 변수 값
    Returns:
      - str: 결정된 publish 모드
    """
    if raw_mode in VALID_WORKER_PUBLISH_MODES:
        return raw_mode
    logger.warning(
        "[Publish Mode] unsupported WORKER_PUBLISH_MODE=%s, "
        "fallback to predict_and_export.",
        raw_mode,
    )
    return "predict_and_export"


def publish_mode_runs_predict(mode: str) -> bool:
    """
    Worker 역할이 predict를 실행하는 지 확인한다.

    Args:
      - mode: 결정된 worker publish 모드
    Returns:
      - bool: predict를 실행하는지 여부
    """
    return mode in {"predict_and_export", "predict_only"}


def publish_mode_runs_export(mode: str) -> bool:
    """
    Worker 역할이 export를 실행하는 지 확인한다.

    Args:
      - mode: 결정된 worker publish 모드
    Returns:
      - bool: export를 실행하는지 여부
    """
    return mode in {"predict_and_export", "export_only"}


def send_alert(message):
    """
    디스코드/슬랙 등으로 알림 전송

    TODO: Worker 기능(Ingest, predict, export)별로 분리된 알림 전송 기능 구현
    """
    if not DISCORD_WEBHOOK_URL:
        logger.warning(f"[Alert Ignored] {message}")
        return

    try:
        payload = {"content": f"**Coin Predict Worker Alert**\n```{message}```"}
        requests.post(DISCORD_WEBHOOK_URL, json=payload, timeout=5)
    except Exception as e:
        logger.error(f"Failed to send alert: {e}")


def _prediction_health_key(symbol: str, timeframe: str) -> str:
    """
    prediction health 엔트리의 고유 키.

    Args:
      - symbol: 심볼
      - timeframe: 타임프레임
    Returns:
      - str: prediction health 엔트리의 고유 키
    """
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

    TODO: Legacy 제거

    Args:
      - kind: 산출물 종류
      - symbol: 심볼
      - timeframe: 타임프레임 (1m, 1h, 1d, 1w, 1M)
      - static_dir: 정적 산출물 디렉토리
    Returns:
      - tuple[Path, Path | None]: (canonical, legacy)
    """
    safe_symbol = symbol.replace("/", "_")
    resolved_static_dir = static_dir or STATIC_DIR
    canonical = resolved_static_dir / f"{kind}_{safe_symbol}_{timeframe}.json"
    legacy = resolved_static_dir / f"{kind}_{safe_symbol}.json"
    if canonical == legacy:
        return canonical, None
    return canonical, legacy


def prediction_enabled_for_timeframe(timeframe: str) -> bool:
    """
    timeframe별 prediction 생성 허용 여부.
    PREDICTION_DISABLED_TIMEFRAMES:
      - 웬만하면 1m. 1m은 predict 데이터의 의미가 거의 없을 것이라 기대.

    Args:
      - timeframe: 타임프레임 (1m, 1h, 1d, 1w, 1M)
    Returns:
      - bool: prediction 생성 허용 여부
    """
    return timeframe not in PREDICTION_DISABLED_TIMEFRAMES


def _load_prediction_health(
    path: Path = PREDICTION_HEALTH_FILE,
) -> dict[str, dict] | dict[None]:
    """
    Prediction health 파일 로드.
    Error 발생 시 빈 dict 반환.

    Args:
      - path: Prediction health 파일 경로
    Returns:
      - dict[str, dict] | dict[None]: Prediction health 정보
    Prediction_health.json 파일 구조:
      {
        "version": 1,
        "updated_at": "2022-01-01T00:00:00Z",
        "entries": {
          "BTC/USDT_1h": {
            "symbol": "BTC/USDT",
            "timeframe": "1h",
            "degraded": false,
            "last_success_at": "2022-01-01T00:00:00Z",
            "last_failure_at": "2022-01-01T00:00:00Z",
            "consecutive_failures": 0,
            "last_error": null,
            "updated_at": "2022-01-01T00:00:00Z"
          }
        }, ...
      }
    """
    return predict_ops.load_prediction_health(_ctx(), path=path)


def _save_prediction_health(
    entries: dict[str, dict], path: Path = PREDICTION_HEALTH_FILE
) -> None:
    """
    Prediction health 파일 저장.

    Args:
      - entries: Prediction health 정보
      - path: Prediction health 파일 경로
    """
    predict_ops.save_prediction_health(_ctx(), entries, path=path)


def _format_utc(dt: datetime | None) -> str | None:
    """
    UTC datetime을 ISO 8601 형식의 문자열로 변환한다.

    Args:
      - dt: UTC datetime 객체
    Returns:
      - str: ISO 8601 형식의 문자열
    """
    return format_utc_datetime(dt)


def _load_symbol_activation(
    path: Path = SYMBOL_ACTIVATION_FILE,
) -> dict[str, SymbolActivationSnapshot]:
    """
    각 심볼의 활성화 여부를 담은 파일 로드.
    Error 발생 시 빈 dict 반환.

    Args:
      - path: Symbol activation 파일 경로
    Returns:
      - dict[str, dict]: Symbol activation 정보
    Symbol_activation.json 파일 구조:
      {
        "version": 1,
        "updated_at": "2022-01-01T00:00:00Z",
        "entries": {
          "BTC/USDT": {
            "symbol": "BTC/USDT",
            "state": "ready_for_serving",
            "visibility": "visible",
            "is_full_backfilled": true,
            "coverage_start_at": "2017-08-17T04:00:00Z",
            "coverage_end_at": "2026-02-17T08:00:00Z",
            "exchange_earliest_at": "2017-08-17T04:00:00Z",
            "ready_at": "2026-02-17T07:19:03Z",
            "updated_at": "2026-02-17T10:00:00Z"
          }
        }, ...
      }
    """
    store = SymbolActivationStore(path, logger)
    return store.load()


def _save_symbol_activation(
    entries: dict[str, SymbolActivationSnapshot | dict],
    path: Path = SYMBOL_ACTIVATION_FILE,
) -> None:
    """
    symbol activation 스냅샷을 파일에 저장한다.

    Called from:
    - run_worker() ingest stage 후반
    """
    store = SymbolActivationStore(path, logger)
    store.save(entries)


def _load_watermark_entries(path: Path) -> dict[str, WatermarkCursor]:
    """
    watermark 파일을 로드하고 유효 엔트리만 정규화해 반환한다.

    Called from:
    - run_worker() 시작/주기 갱신

    Why:
    - 손상/잡음 엔트리를 무시해 gate 판단 안정성을 유지한다.
    """
    store = WatermarkStore(path, logger)
    return store.load()


def _save_watermark_entries(
    entries: dict[str, WatermarkCursor | str], path: Path
) -> None:
    """
    watermark 엔트리를 파일에 저장한다.

    Called from:
    - run_worker() stage 완료 후 cursor commit
    """
    store = WatermarkStore(path, logger)
    store.save(entries)


def _parse_utc(text: str | None) -> datetime | None:
    """
    UTC 문자열을 datetime으로 파싱한다.

    Called from:
    - should_run_publish_from_ingest_watermark
    """
    return parse_utc_datetime(text)


def _resolve_watermark_datetime(
    raw_entry: WatermarkCursor | str | None,
) -> datetime | None:
    """
    watermark entry raw 값을 datetime으로 정규화한다.
    """
    if isinstance(raw_entry, WatermarkCursor):
        return raw_entry.closed_at
    if isinstance(raw_entry, str):
        return _parse_utc(raw_entry)
    return None


def _upsert_watermark(
    entries: dict[str, WatermarkCursor | str],
    *,
    symbol: str,
    timeframe: str,
    closed_at: datetime,
) -> None:
    """
    Watermark에 새로운 closed_at을 기록한다.

    XXX: entries를 직접 수정하는 방식이 적절한가?
    Args:
      - entries: Watermark entries
      - symbol: 심볼
      - timeframe: 타임프레임
      - closed_at: closed_at
    """
    key = _prediction_health_key(symbol, timeframe)
    entries[key] = WatermarkCursor(
        symbol=symbol,
        timeframe=timeframe,
        closed_at=closed_at,
    )


def evaluate_publish_gate_from_ingest_watermark(
    *,
    symbol: str,
    timeframe: str,
    ingest_entries: dict[str, WatermarkCursor | str],
    publish_entries: dict[str, WatermarkCursor | str],
) -> PublishGateDecision:
    """
    ingest watermark 기준 publish 실행 여부를 DTO로 판단한다.
    """
    key = _prediction_health_key(symbol, timeframe)
    ingest_dt = _resolve_watermark_datetime(ingest_entries.get(key))
    if ingest_dt is None:
        return PublishGateDecision(
            should_run=False,
            reason=PublishGateReason.NO_INGEST_WATERMARK,
            ingest_closed_at=None,
        )

    publish_dt = _resolve_watermark_datetime(publish_entries.get(key))
    if publish_dt is not None and publish_dt >= ingest_dt:
        return PublishGateDecision(
            should_run=False,
            reason=PublishGateReason.UP_TO_DATE_INGEST_WATERMARK,
            ingest_closed_at=ingest_dt,
        )
    return PublishGateDecision(
        should_run=True,
        reason=PublishGateReason.INGEST_WATERMARK_ADVANCED,
        ingest_closed_at=ingest_dt,
    )


def should_run_publish_from_ingest_watermark(
    *,
    symbol: str,
    timeframe: str,
    ingest_entries: dict[str, WatermarkCursor | str],
    publish_entries: dict[str, WatermarkCursor | str],
) -> tuple[bool, str, datetime | None]:
    """
    Publish가 실행되어야 하는지 판단한다.

    Args:
      - symbol: 심볼
      - timeframe: 타임프레임
      - ingest_entries: Ingest watermark entries
      - publish_entries: Publish watermark entries
    Returns:
      - tuple[bool, str, datetime | None]: (should_run, reason, ingest_dt)
    """
    decision = evaluate_publish_gate_from_ingest_watermark(
        symbol=symbol,
        timeframe=timeframe,
        ingest_entries=ingest_entries,
        publish_entries=publish_entries,
    )
    return (
        decision.should_run,
        decision.reason.value,
        decision.ingest_closed_at,
    )


def _default_symbol_activation_entry(
    symbol: str, now: datetime
) -> SymbolActivationSnapshot:
    """
    Predict/export 전용 worker가 activation 파일을 아직 받지 못한 경우를
    보수적으로 처리하기 위한 기본값(숨김) 엔트리.
    """
    return SymbolActivationSnapshot.from_payload(
        symbol=symbol,
        payload={
            "symbol": symbol,
            "state": "registered",
            "visibility": "hidden_backfilling",
            "is_full_backfilled": False,
            "coverage_start_at": None,
            "coverage_end_at": None,
            "exchange_earliest_at": None,
            "ready_at": None,
            "updated_at": _format_utc(now) or "",
        },
        fallback_now=now,
    )


def _remove_static_exports_for_symbol(
    symbol: str, timeframes: list[str], *, static_dir: Path = STATIC_DIR
) -> None:
    """
    심볼의 정적 산출물(history/prediction)을 제거한다.

    Called from:
    - run_worker()에서 hidden_backfilling 심볼 처리 시점

    Why:
    - full backfill 전 심볼의 오노출을 fail-closed로 차단하기 위함이다.
    """
    for timeframe in timeframes:
        for kind in ("history", "prediction"):
            canonical_path, legacy_path = _static_export_paths(
                kind, symbol, timeframe, static_dir=static_dir
            )
            for path in (canonical_path, legacy_path):
                if path is None:
                    continue
                try:
                    path.unlink(missing_ok=True)
                except OSError as e:
                    logger.warning(
                        f"[{symbol} {timeframe}] failed to remove static file {path}: {e}"
                    )


def _load_runtime_metrics(path: Path = RUNTIME_METRICS_FILE) -> list[dict]:
    """
    런타임 메트릭스를 리턴한다.

    Args:
      - path: 런타임 메트릭스 파일 경로
    Returns:
      - list[dict]: 런타임 메트릭스

    Example:
        recent_cycles: [
            {
                started_at: 2026-02-17T04:43:11Z,
                elapsed_seconds: 8.96,
                sleep_seconds: 51.04,
                overrun: false,
                result: ok,
                error: null
            }, ...
        ]
    """
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
    """
    Args:
      - values: 값 리스트
      - q: 백분위수
    Returns:
      - float | None: 백분위수 값
    """
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


def _normalize_source_counts(
    raw_counts: dict | None,
) -> dict[str, int] | dict[None]:
    """
    Args:
      - raw_counts: 원시 소스 카운트
    Returns:
      - dict[str, int]: 정규화된 소스 카운트
    """
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


def _aggregate_ingest_source_metrics(
    entries: list[dict],
) -> dict[str, int | dict]:
    """
    Args:
      - entries: 런타임 메트릭스 (recent_cycles; _load_runtime_metrics)
    Returns:
      - dict[str, int | dict]: 집계된 소스 메트릭스
    """
    source_counts: dict[str, int] = {}
    rebootstrap_cycles = 0
    rebootstrap_events = 0
    underfill_guard_retrigger_cycles = 0
    underfill_guard_retrigger_events = 0

    for item in entries:
        counts = _normalize_source_counts(
            item.get("ingest_since_source_counts")
        )
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


def _aggregate_reason_counts(
    entries: list[dict], field_name: str
) -> dict[str, int]:
    """
    Args:
      - entries: run_time_metrics; recent_cycles
      - field_name: 집계할 필드 이름
    Returns:
      - dict[str, int]: 집계된 카운트
    """
    merged: dict[str, int] = {}
    for item in entries:
        counts = _normalize_source_counts(item.get(field_name))
        for reason, count in counts.items():
            merged[reason] = merged.get(reason, 0) + count
    return merged


def initialize_boundary_schedule(
    now: datetime, timeframes: list[str]
) -> dict[str, datetime]:
    """
    각 timeframe의 다음 경계를 초기 스케줄로 설정한다.

    Called from:
    - run_worker() 시작 시(경계 스케줄러 모드)
    """
    # 각 timeframe의 "다음 경계"를 기준점으로 잡는다.
    # 시작 시각을 now 그대로 쓰지 않는 이유는 경계 정렬을 강제해
    # poll drift(누적 시간 오차)를 줄이기 위함이다.
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
    """
    현재 시각 기준으로 실행 due timeframe과 missed boundary 수를 계산한다.

    Called from:
    - run_worker() cycle 시작부
    """
    due_timeframes: list[str] = []
    missed_boundary_count = 0

    for timeframe in timeframes:
        next_boundary = next_boundary_by_timeframe.get(timeframe)
        if next_boundary is None:
            next_boundary = next_timeframe_boundary(now, timeframe)
            next_boundary_by_timeframe[timeframe] = next_boundary

        # 봉 마감 미완료 된 데이터
        if now < next_boundary:
            continue

        due_timeframes.append(timeframe)
        boundary_advance_steps = 0
        while next_boundary <= now:
            # 워커 중단/지연 후 복귀 시 경계를 여러 개 건너뛸 수 있다.
            # while로 다음 경계까지 따라잡고, 몇 개를 놓쳤는지 계측해
            # 운영자가 missed boundary를 관찰할 수 있게 한다.
            next_boundary = next_timeframe_boundary(next_boundary, timeframe)
            boundary_advance_steps += 1

        # 원본 변경
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
    """
    cycle 메트릭을 recent window에 누적하고 요약 통계를 갱신한다.

    Called from:
    - run_worker() 정상/idle/실패 cycle 종료 시점

    Why:
    - scheduler/gate 변경 효과를 수치로 검증하기 위해 런타임 증거를 남긴다.
    """
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
    sleep_values = [float(item.get("sleep_seconds", 0.0)) for item in entries]
    avg_elapsed = round(sum(elapsed_values) / samples, 2) if samples else None
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
        "updated_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
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
    prediction health 업데이트 래퍼.

    Called from:
    - run_worker() predict stage 결과 처리
    """
    return predict_ops.upsert_prediction_health(
        _ctx(),
        symbol=symbol,
        timeframe=timeframe,
        prediction_ok=prediction_ok,
        error=error,
        path=path,
    )


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
    """
    디스크 사용률(%)을 계산한다.

    Called from:
    - run_worker() ingest stage의 storage guard
    """
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
    """
    사용률을 watermark level(normal/warn/critical/block)로 변환한다.

    Called from:
    - run_worker() storage guard
    """
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
    """
    1m retention 실행 주기가 도래했는지 판단한다.

    Called from:
    - run_worker() cycle 초반
    """
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
    """
    디스크 block 상태에서 1m 초기 백필 차단 여부를 반환한다.

    Called from:
    - resolve_ingest_since
    """
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
    ingest since 판정 래퍼.

    Called from:
    - run_worker() 각 symbol/timeframe ingest 직전
    """
    return ingest_ops.resolve_ingest_since(
        _ctx(),
        symbol=symbol,
        timeframe=timeframe,
        state_since=state_since,
        last_time=last_time,
        disk_level=disk_level,
        force_rebootstrap=force_rebootstrap,
        bootstrap_since=bootstrap_since,
        enforce_full_backfill=enforce_full_backfill,
        now=now,
    )


def _minimum_required_lookback_rows(
    timeframe: str, lookback_days: int
) -> int | None:
    """
    coverage underfill 최소 row 기준 계산 래퍼.

    Called from:
    - run_worker() underfill guard
    """
    return ingest_ops.minimum_required_lookback_rows(
        _ctx(), timeframe, lookback_days
    )


def get_lookback_close_count(
    query_api, symbol: str, timeframe: str, lookback_days: int
) -> int | None:
    """
    lookback close row count 조회 래퍼.

    Called from:
    - run_worker() underfill guard
    """
    return ingest_ops.get_lookback_close_count(
        _ctx(), query_api, symbol, timeframe, lookback_days
    )


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
    """
    downsample lineage 파일 로드.

    Called from:
    - upsert_downsample_lineage
    """
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
    """
    downsample lineage 파일 저장.

    Called from:
    - upsert_downsample_lineage
    """
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
    """
    심볼/타임프레임별 downsample lineage 스냅샷을 갱신한다.

    Called from:
    - workers.ingest.run_downsample_and_save
    """
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
    """
    downsample source 조회 래퍼.

    Called from:
    - run_downsample_and_save wrapper 경유 테스트/호환 경로
    """
    return ingest_ops.query_ohlcv_frame(
        _ctx(),
        query_api,
        symbol=symbol,
        timeframe=timeframe,
        lookback_days=lookback_days,
    )


def downsample_ohlcv_frame(
    source_df: pd.DataFrame,
    *,
    target_timeframe: str,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """
    downsample 집계 래퍼.

    Called from:
    - run_downsample_and_save wrapper 경유 테스트/호환 경로
    """
    return ingest_ops.downsample_ohlcv_frame(
        _ctx(), source_df, target_timeframe=target_timeframe
    )


def run_downsample_and_save(
    write_api,
    query_api,
    *,
    symbol: str,
    target_timeframe: str,
) -> tuple[datetime | None, str]:
    """
    derived timeframe materialization 래퍼.

    Called from:
    - run_ingest_step
    """
    return ingest_ops.run_downsample_and_save(
        _ctx(),
        write_api,
        query_api,
        symbol=symbol,
        target_timeframe=target_timeframe,
    )


def run_ingest_step(
    write_api,
    query_api,
    *,
    symbol: str,
    timeframe: str,
    since: datetime | None,
) -> tuple[datetime | None, str]:
    """
    timeframe routing boundary:
    - base timeframe(`1m`,`1h`): exchange ingest
    - derived timeframe(`1d`,`1w`,`1M`): downsample materialization only
    """
    if timeframe in DOWNSAMPLE_TARGET_TIMEFRAMES:
        return run_downsample_and_save(
            write_api,
            query_api,
            symbol=symbol,
            target_timeframe=timeframe,
        )
    return fetch_and_save(write_api, symbol, since, timeframe)


def run_ingest_step_outcome(
    write_api,
    query_api,
    *,
    symbol: str,
    timeframe: str,
    since: datetime | None,
) -> IngestExecutionOutcome:
    """
    ingest 단계 문자열 결과를 Enum 상태로 정규화한다.
    """
    latest_saved_at, raw_result = run_ingest_step(
        write_api,
        query_api,
        symbol=symbol,
        timeframe=timeframe,
        since=since,
    )
    return IngestExecutionOutcome(
        latest_saved_at=latest_saved_at,
        result=parse_ingest_execution_result(raw_result),
    )


def _static_export_candidates(
    kind: str,
    symbol: str,
    timeframe: str,
    static_dir: Path | None = None,
) -> list[Path]:
    """
    정적 export 후보(canonical/legacy) 경로 반환 래퍼.

    Called from:
    - build_runtime_manifest wrapper 경유
    """
    return export_ops.static_export_candidates(
        _ctx(),
        kind=kind,
        symbol=symbol,
        timeframe=timeframe,
        static_dir=static_dir,
    )


def _extract_updated_at_from_files(
    candidates: list[Path],
) -> tuple[str | None, str | None]:
    """
    후보 파일의 updated_at 추출 래퍼.

    Called from:
    - build_runtime_manifest wrapper 경유
    """
    return export_ops.extract_updated_at_from_files(_ctx(), candidates)


def build_runtime_manifest(
    symbols: list[str],
    timeframes: list[str],
    *,
    now: datetime | None = None,
    static_dir: Path | None = None,
    prediction_health_path: Path | None = None,
    symbol_activation_entries: (
        dict[str, SymbolActivationSnapshot | dict] | None
    ) = None,
) -> dict:
    """
    runtime manifest 생성 래퍼.

    Called from:
    - write_runtime_manifest
    """
    serialized_activation_entries: dict[str, dict] | None = None
    if symbol_activation_entries is not None:
        serialized_activation_entries = {}
        for symbol, entry in symbol_activation_entries.items():
            if isinstance(entry, SymbolActivationSnapshot):
                serialized_activation_entries[symbol] = entry.to_payload()
            elif isinstance(entry, dict):
                serialized_activation_entries[symbol] = entry

    return export_ops.build_runtime_manifest(
        _ctx(),
        symbols,
        timeframes,
        now=now,
        static_dir=static_dir,
        prediction_health_path=prediction_health_path,
        symbol_activation_entries=serialized_activation_entries,
    )


def write_runtime_manifest(
    symbols: list[str],
    timeframes: list[str],
    *,
    now: datetime | None = None,
    static_dir: Path | None = None,
    prediction_health_path: Path | None = None,
    symbol_activation_entries: (
        dict[str, SymbolActivationSnapshot | dict] | None
    ) = None,
    path: Path | None = None,
) -> None:
    """
    runtime manifest 저장 래퍼.

    Called from:
    - run_worker() export stage 완료 시점
    """
    serialized_activation_entries: dict[str, dict] | None = None
    if symbol_activation_entries is not None:
        serialized_activation_entries = {}
        for symbol, entry in symbol_activation_entries.items():
            if isinstance(entry, SymbolActivationSnapshot):
                serialized_activation_entries[symbol] = entry.to_payload()
            elif isinstance(entry, dict):
                serialized_activation_entries[symbol] = entry

    export_ops.write_runtime_manifest(
        _ctx(),
        symbols,
        timeframes,
        now=now,
        static_dir=static_dir,
        prediction_health_path=prediction_health_path,
        symbol_activation_entries=serialized_activation_entries,
        path=path,
    )


def _query_last_timestamp(query_api, query: str) -> datetime | None:
    """
    last timestamp 쿼리 래퍼.

    Called from:
    - get_last_timestamp wrapper
    """
    return ingest_ops.query_last_timestamp(query_api, query)


def _query_first_timestamp(query_api, query: str) -> datetime | None:
    """
    first timestamp 쿼리 래퍼.

    Called from:
    - get_first_timestamp wrapper
    """
    return ingest_ops.query_first_timestamp(query_api, query)


def get_first_timestamp(
    query_api, symbol: str, timeframe: str
) -> datetime | None:
    """
    DB earliest 조회 래퍼.

    Called from:
    - build_symbol_activation_entry
    """
    return ingest_ops.get_first_timestamp(_ctx(), query_api, symbol, timeframe)


def get_last_timestamp(
    query_api, symbol, timeframe, *, full_range: bool = False
):
    """
    DB latest 조회 래퍼.

    Called from:
    - run_worker() ingest/detection/activation 판단
    """
    return ingest_ops.get_last_timestamp(
        _ctx(), query_api, symbol, timeframe, full_range=full_range
    )


def get_exchange_earliest_closed_timestamp(
    exchange,
    symbol: str,
    timeframe: str,
    *,
    now: datetime | None = None,
) -> datetime | None:
    """
    거래소 earliest closed 조회 래퍼.

    Called from:
    - run_worker() symbol activation 계산
    """
    return ingest_ops.get_exchange_earliest_closed_timestamp(
        _ctx(),
        exchange,
        symbol,
        timeframe,
        now=now,
    )


def get_exchange_latest_closed_timestamp(
    exchange,
    symbol: str,
    timeframe: str,
    *,
    now: datetime | None = None,
) -> datetime | None:
    """
    거래소 latest closed 조회 래퍼.

    Called from:
    - evaluate_detection_gate
    """
    return ingest_ops.get_exchange_latest_closed_timestamp(
        _ctx(),
        exchange,
        symbol,
        timeframe,
        now=now,
    )


def evaluate_detection_gate(
    query_api,
    detection_exchange,
    *,
    symbol: str,
    timeframe: str,
    now: datetime,
    last_saved: datetime | None = None,
) -> tuple[bool, str]:
    """
    boundary+detection gate 판단 래퍼.

    Called from:
    - run_worker() scheduler_mode=boundary
    """
    decision = ingest_ops.evaluate_detection_gate(
        _ctx(),
        query_api,
        detection_exchange,
        symbol=symbol,
        timeframe=timeframe,
        now=now,
        last_saved=last_saved,
    )
    return decision.should_run, decision.reason.value


def evaluate_detection_gate_decision(
    query_api,
    detection_exchange,
    *,
    symbol: str,
    timeframe: str,
    now: datetime,
    last_saved: datetime | None = None,
) -> DetectionGateDecision:
    """
    detection gate 결과를 DTO로 반환한다.
    """
    return ingest_ops.evaluate_detection_gate(
        _ctx(),
        query_api,
        detection_exchange,
        symbol=symbol,
        timeframe=timeframe,
        now=now,
        last_saved=last_saved,
    )


def build_symbol_activation_entry(
    *,
    query_api,
    symbol: str,
    now: datetime,
    exchange_earliest: datetime | None,
    existing_entry: SymbolActivationSnapshot | dict | None = None,
) -> SymbolActivationSnapshot:
    """
    symbol activation 상태 계산 래퍼.

    Called from:
    - run_worker() per symbol
    """
    return ingest_ops.build_symbol_activation_entry(
        _ctx(),
        query_api=query_api,
        symbol=symbol,
        now=now,
        exchange_earliest=exchange_earliest,
        existing_entry=existing_entry,
    )


def save_history_to_json(df, symbol, timeframe):
    """
    history JSON 저장 래퍼.

    Called from:
    - update_full_history_file wrapper 경유
    """
    export_ops.save_history_to_json(_ctx(), df, symbol, timeframe)


def fetch_and_save(
    write_api, symbol, since_ts, timeframe
) -> tuple[datetime | None, str]:
    """
    base ingest 실행 래퍼.

    Called from:
    - run_ingest_step
    """
    return ingest_ops.fetch_and_save(
        _ctx(), write_api, symbol, since_ts, timeframe
    )


def _fetch_ohlcv_paginated(
    exchange, symbol: str, timeframe: str, since_ms: int, until_ms: int
) -> tuple[pd.DataFrame, int]:
    """
    거래소 페이지 조회 래퍼.

    Called from:
    - tests/호환 코드 경유
    """
    return ingest_ops.fetch_ohlcv_paginated(
        _ctx(),
        exchange=exchange,
        symbol=symbol,
        timeframe=timeframe,
        since_ms=since_ms,
        until_ms=until_ms,
    )


def _detect_gaps_from_ms_timestamps(timestamps_ms: list[int], timeframe: str):
    """
    gap 탐지 래퍼.

    Called from:
    - tests/호환 코드 경유
    """
    return ingest_ops.detect_gaps_from_ms_timestamps(
        _ctx(), timestamps_ms=timestamps_ms, timeframe=timeframe
    )


def _refill_detected_gaps(
    exchange,
    symbol: str,
    timeframe: str,
    source_df: pd.DataFrame,
    gaps,
    last_closed_ms: int,
) -> tuple[pd.DataFrame, int]:
    """
    gap refill 래퍼.

    Called from:
    - tests/호환 코드 경유
    """
    return ingest_ops.refill_detected_gaps(
        _ctx(),
        exchange=exchange,
        symbol=symbol,
        timeframe=timeframe,
        source_df=source_df,
        gaps=gaps,
        last_closed_ms=last_closed_ms,
    )


def run_prediction_and_save(
    write_api, symbol, timeframe
) -> tuple[str, str | None]:
    """
    prediction 실행 래퍼.

    Called from:
    - run_worker() predict stage
    """
    return predict_ops.run_prediction_and_save(
        _ctx(), write_api, symbol, timeframe
    )


def run_prediction_and_save_outcome(
    write_api,
    symbol: str,
    timeframe: str,
) -> PredictionExecutionOutcome:
    """
    prediction 단계 문자열 결과를 Enum 상태로 정규화한다.
    """
    raw_result, prediction_error = run_prediction_and_save(
        write_api,
        symbol,
        timeframe,
    )
    return PredictionExecutionOutcome(
        result=parse_prediction_execution_result(raw_result),
        error=prediction_error,
    )


def update_full_history_file(query_api, symbol, timeframe) -> bool:
    """
    history export 실행 래퍼.

    Called from:
    - run_worker() export stage
    """
    return export_ops.update_full_history_file(
        _ctx(), query_api, symbol, timeframe
    )


@dataclass
class WorkerPersistentState:
    """
    cycle 간 유지되는 runtime 상태 집합.
    """

    symbol_activation_entries: dict[str, SymbolActivationSnapshot]
    ingest_watermarks: dict[str, WatermarkCursor | str]
    predict_watermarks: dict[str, WatermarkCursor | str]
    export_watermarks: dict[str, WatermarkCursor | str]


def _coerce_storage_guard_level(raw_level: str) -> StorageGuardLevel:
    """
    문자열 storage level을 Enum으로 정규화한다.
    """
    try:
        return StorageGuardLevel(raw_level)
    except ValueError:
        logger.warning(
            "[Storage Guard] unknown level=%s, fallback to normal.",
            raw_level,
        )
        return StorageGuardLevel.NORMAL


def _log_stage_failure_context(
    stage: str,
    *,
    symbol: str,
    timeframe: str,
    now: datetime,
    last_closed_ts: datetime | None,
    error: str,
    extra: dict | None = None,
) -> None:
    """
    단계 실패 시 공통 컨텍스트 로그를 남긴다.
    """
    context = {
        "stage": stage,
        "symbol": symbol,
        "timeframe": timeframe,
        "now": _format_utc(now),
        "last_closed_ts": _format_utc(last_closed_ts),
    }
    if isinstance(extra, dict) and extra:
        context.update(extra)
    logger.error("Stage failure context=%s error=%s", context, error)


def _prepare_symbol_activation_for_cycle(
    *,
    run_ingest_stage: bool,
    query_api,
    activation_exchange,
    symbol: str,
    cycle_now: datetime,
    state: WorkerPersistentState,
) -> tuple[SymbolActivationSnapshot, datetime | None, bool]:
    """
    심볼 activation 상태를 현재 cycle 기준으로 준비한다.
    """
    exchange_earliest: datetime | None = None
    activation_loaded = False

    if run_ingest_stage:
        exchange_earliest = get_exchange_earliest_closed_timestamp(
            activation_exchange,
            symbol,
            DOWNSAMPLE_SOURCE_TIMEFRAME,
            now=cycle_now,
        )
        activation = build_symbol_activation_entry(
            query_api=query_api,
            symbol=symbol,
            now=cycle_now,
            exchange_earliest=exchange_earliest,
            existing_entry=state.symbol_activation_entries.get(symbol),
        )
        state.symbol_activation_entries[symbol] = activation
        activation_loaded = True
        return activation, exchange_earliest, activation_loaded

    loaded_activation = state.symbol_activation_entries.get(symbol)
    if isinstance(loaded_activation, SymbolActivationSnapshot):
        activation_loaded = True
        return loaded_activation, exchange_earliest, activation_loaded

    if isinstance(loaded_activation, dict):
        normalized = SymbolActivationSnapshot.from_payload(
            symbol=symbol,
            payload=loaded_activation,
            fallback_now=cycle_now,
        )
        state.symbol_activation_entries[symbol] = normalized
        activation_loaded = True
        return normalized, exchange_earliest, activation_loaded

    default_activation = _default_symbol_activation_entry(symbol, cycle_now)
    state.symbol_activation_entries[symbol] = default_activation
    return default_activation, exchange_earliest, activation_loaded


def _run_ingest_timeframe_step(
    *,
    write_api,
    query_api,
    activation_exchange,
    ingest_state_store: IngestStateStore,
    symbol: str,
    timeframe: str,
    cycle_now: datetime,
    scheduler_mode: str,
    symbol_activation: SymbolActivationSnapshot,
    exchange_earliest: datetime | None,
    disk_level: StorageGuardLevel,
    disk_usage_percent: float | None,
    state: WorkerPersistentState,
    cycle_since_source_counts: dict[str, int],
    cycle_detection_skip_counts: dict[str, int],
    cycle_detection_run_counts: dict[str, int],
) -> tuple[bool, SymbolActivationSnapshot]:
    """
    ingest 단계의 symbol+timeframe 처리를 수행한다.

    Returns:
      - tuple[bool, SymbolActivationSnapshot]
        1) publish 단계 진행 여부
        2) 최신 symbol activation 스냅샷
    """
    state_since = ingest_state_store.get_last_closed(symbol, timeframe)
    last_time = get_last_timestamp(query_api, symbol, timeframe)

    if scheduler_mode == "boundary":
        gate_decision = evaluate_detection_gate_decision(
            query_api,
            activation_exchange,
            symbol=symbol,
            timeframe=timeframe,
            now=cycle_now,
            last_saved=last_time,
        )
        gate_reason = gate_decision.reason.value
        if not gate_decision.should_run:
            cycle_detection_skip_counts[gate_reason] = (
                cycle_detection_skip_counts.get(gate_reason, 0) + 1
            )
            logger.info(
                f"[{symbol} {timeframe}] detection gate skip "
                f"(reason={gate_reason})"
            )
            return False, symbol_activation
        cycle_detection_run_counts[gate_reason] = (
            cycle_detection_run_counts.get(gate_reason, 0) + 1
        )

    lookback_days = _lookback_days_for_timeframe(timeframe)
    force_rebootstrap = False
    min_required_rows = _minimum_required_lookback_rows(
        timeframe,
        lookback_days,
    )
    if min_required_rows is not None:
        close_count = get_lookback_close_count(
            query_api,
            symbol,
            timeframe,
            lookback_days,
        )
        if close_count is not None and close_count < min_required_rows:
            force_rebootstrap = True
            logger.warning(
                f"[{symbol} {timeframe}] canonical coverage underfilled: "
                f"close_count={close_count} < min_required={min_required_rows}. "
                "Rebootstrapping from lookback."
            )

    since, since_source_text = resolve_ingest_since(
        symbol=symbol,
        timeframe=timeframe,
        state_since=state_since,
        last_time=last_time,
        disk_level=disk_level.value,
        force_rebootstrap=force_rebootstrap,
        bootstrap_since=(
            exchange_earliest
            if timeframe == DOWNSAMPLE_SOURCE_TIMEFRAME
            else None
        ),
        enforce_full_backfill=(
            timeframe == DOWNSAMPLE_SOURCE_TIMEFRAME
            and symbol_activation.visibility
            == SymbolVisibility.HIDDEN_BACKFILLING
        ),
        now=cycle_now,
    )
    cycle_since_source_counts[since_source_text] = (
        cycle_since_source_counts.get(since_source_text, 0) + 1
    )
    since_source = parse_ingest_since_source(since_source_text)

    if since_source == IngestSinceSource.BLOCKED_STORAGE_GUARD:
        logger.warning(
            f"[{symbol} {timeframe}] initial backfill blocked "
            f"by storage guard (usage={disk_usage_percent}%)."
        )
        ingest_state_store.upsert(
            symbol,
            timeframe,
            last_closed_ts=state_since,
            status=IngestSinceSource.BLOCKED_STORAGE_GUARD.value,
        )
        return False, symbol_activation

    if is_rebootstrap_source(since_source):
        if (
            since_source == IngestSinceSource.BOOTSTRAP_EXCHANGE_EARLIEST
            or since_source == IngestSinceSource.FULL_BACKFILL_EXCHANGE_EARLIEST
            or since_source
            == IngestSinceSource.STATE_DRIFT_REBOOTSTRAP_EXCHANGE_EARLIEST
        ):
            logger.info(
                f"[{symbol} {timeframe}] 초기 데이터 수집 시작 "
                f"(source={since_source_text}, since={_format_utc(since)})"
            )
        else:
            logger.info(
                f"[{symbol} {timeframe}] 초기 데이터 수집 시작 "
                f"({lookback_days}일 전부터, source={since_source_text})"
            )

    ingest_outcome = run_ingest_step_outcome(
        write_api,
        query_api,
        symbol=symbol,
        timeframe=timeframe,
        since=since,
    )
    if ingest_outcome.result == IngestExecutionResult.SAVED:
        ingest_state_store.upsert(
            symbol,
            timeframe,
            last_closed_ts=ingest_outcome.latest_saved_at,
            status="ok",
        )
        if ingest_outcome.latest_saved_at is not None:
            _upsert_watermark(
                state.ingest_watermarks,
                symbol=symbol,
                timeframe=timeframe,
                closed_at=ingest_outcome.latest_saved_at,
            )
    elif ingest_outcome.result == IngestExecutionResult.FAILED:
        ingest_state_store.upsert(
            symbol,
            timeframe,
            last_closed_ts=state_since,
            status="failed",
        )
        _log_stage_failure_context(
            "ingest",
            symbol=symbol,
            timeframe=timeframe,
            now=cycle_now,
            last_closed_ts=state_since,
            error="ingest_result_failed",
            extra={
                "since_source": since_source_text,
                "requested_since": _format_utc(since),
            },
        )
    elif ingest_outcome.result == IngestExecutionResult.UNSUPPORTED:
        ingest_state_store.upsert(
            symbol,
            timeframe,
            last_closed_ts=state_since,
            status="failed",
        )
        _log_stage_failure_context(
            "ingest",
            symbol=symbol,
            timeframe=timeframe,
            now=cycle_now,
            last_closed_ts=state_since,
            error="unsupported_timeframe",
            extra={"requested_since": _format_utc(since)},
        )

    if (
        timeframe == DOWNSAMPLE_SOURCE_TIMEFRAME
        and symbol_activation.visibility == SymbolVisibility.HIDDEN_BACKFILLING
    ):
        refreshed_activation = build_symbol_activation_entry(
            query_api=query_api,
            symbol=symbol,
            now=cycle_now,
            exchange_earliest=exchange_earliest,
            existing_entry=state.symbol_activation_entries.get(symbol),
        )
        state.symbol_activation_entries[symbol] = refreshed_activation
        if (
            refreshed_activation.visibility
            == SymbolVisibility.HIDDEN_BACKFILLING
        ):
            _remove_static_exports_for_symbol(
                symbol,
                TIMEFRAMES,
                static_dir=STATIC_DIR,
            )
        return True, refreshed_activation

    return True, symbol_activation


def _run_publish_timeframe_step(
    *,
    write_api,
    query_api,
    symbol: str,
    timeframe: str,
    cycle_now: datetime,
    symbol_activation: SymbolActivationSnapshot,
    run_export_stage: bool,
    run_predict_stage: bool,
    state: WorkerPersistentState,
    cycle_export_gate_skip_counts: dict[str, int],
    cycle_predict_gate_skip_counts: dict[str, int],
) -> None:
    """
    publish 단계의 symbol+timeframe 처리를 수행한다.
    """
    if symbol_activation.visibility == SymbolVisibility.HIDDEN_BACKFILLING:
        logger.info(
            f"[{symbol}] activation state={symbol_activation.state.value} "
            "-> skip static export/prediction for FE hide policy."
        )
        _remove_static_exports_for_symbol(
            symbol,
            [timeframe],
            static_dir=STATIC_DIR,
        )
        return

    if run_export_stage:
        export_decision = evaluate_publish_gate_from_ingest_watermark(
            symbol=symbol,
            timeframe=timeframe,
            ingest_entries=state.ingest_watermarks,
            publish_entries=state.export_watermarks,
        )
        export_gate_reason = export_decision.reason.value
        if not export_decision.should_run:
            cycle_export_gate_skip_counts[export_gate_reason] = (
                cycle_export_gate_skip_counts.get(export_gate_reason, 0) + 1
            )
        else:
            export_ok = update_full_history_file(query_api, symbol, timeframe)
            if export_ok and export_decision.ingest_closed_at is not None:
                _upsert_watermark(
                    state.export_watermarks,
                    symbol=symbol,
                    timeframe=timeframe,
                    closed_at=export_decision.ingest_closed_at,
                )
            elif not export_ok:
                _log_stage_failure_context(
                    "export",
                    symbol=symbol,
                    timeframe=timeframe,
                    now=cycle_now,
                    last_closed_ts=export_decision.ingest_closed_at,
                    error="export_result_failed",
                    extra={"gate_reason": export_gate_reason},
                )
                logger.warning(
                    f"[{symbol} {timeframe}] export failed. "
                    "watermark cursor is not advanced."
                )

    if run_predict_stage:
        predict_decision = evaluate_publish_gate_from_ingest_watermark(
            symbol=symbol,
            timeframe=timeframe,
            ingest_entries=state.ingest_watermarks,
            publish_entries=state.predict_watermarks,
        )
        predict_gate_reason = predict_decision.reason.value
        if not predict_decision.should_run:
            cycle_predict_gate_skip_counts[predict_gate_reason] = (
                cycle_predict_gate_skip_counts.get(predict_gate_reason, 0) + 1
            )
            return

        prediction_outcome = run_prediction_and_save_outcome(
            write_api,
            symbol,
            timeframe,
        )
        if prediction_outcome.result == PredictionExecutionResult.FAILED:
            _log_stage_failure_context(
                "predict",
                symbol=symbol,
                timeframe=timeframe,
                now=cycle_now,
                last_closed_ts=predict_decision.ingest_closed_at,
                error=prediction_outcome.error or "prediction_failed",
                extra={"gate_reason": predict_gate_reason},
            )
            logger.warning(
                f"[{symbol} {timeframe}] prediction failed. "
                "watermark cursor is not advanced."
            )
            return

        if predict_decision.ingest_closed_at is not None:
            _upsert_watermark(
                state.predict_watermarks,
                symbol=symbol,
                timeframe=timeframe,
                closed_at=predict_decision.ingest_closed_at,
            )

        if prediction_outcome.result == PredictionExecutionResult.SKIPPED:
            return

        prediction_ok = (
            prediction_outcome.result == PredictionExecutionResult.OK
        )
        health, was_degraded, is_degraded = upsert_prediction_health(
            symbol,
            timeframe,
            prediction_ok=prediction_ok,
            error=prediction_outcome.error,
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
            logger.info(f"[{symbol} {timeframe}] prediction recovered.")
            send_alert(
                "[Predict Recovery] "
                f"{symbol} {timeframe}\n"
                f"last_success_at={health.get('last_success_at')}"
            )
        elif is_degraded:
            logger.info(
                f"[{symbol} {timeframe}] prediction still degraded "
                f"(consecutive_failures={health.get('consecutive_failures')})"
            )


def _persist_cycle_runtime_state(
    *,
    run_ingest_stage: bool,
    run_predict_stage: bool,
    run_export_stage: bool,
    state: WorkerPersistentState,
) -> None:
    """
    cycle 종료 시 runtime state 파일을 저장한다.
    """
    if run_ingest_stage:
        try:
            _save_symbol_activation(state.symbol_activation_entries)
            _save_watermark_entries(
                state.ingest_watermarks,
                INGEST_WATERMARK_FILE,
            )
        except Exception as e:
            logger.error(f"Symbol activation update failed: {e}")
            send_alert(f"[Symbol Activation Error] {e}")

    if run_predict_stage:
        try:
            _save_watermark_entries(
                state.predict_watermarks,
                PREDICT_WATERMARK_FILE,
            )
        except Exception as e:
            logger.error(f"Predict watermark update failed: {e}")
            send_alert(f"[Predict Watermark Error] {e}")

    if run_export_stage:
        try:
            _save_watermark_entries(
                state.export_watermarks,
                EXPORT_WATERMARK_FILE,
            )
            write_runtime_manifest(
                TARGET_COINS,
                TIMEFRAMES,
                symbol_activation_entries=state.symbol_activation_entries,
            )
        except Exception as e:
            logger.error(f"Runtime manifest update failed: {e}")
            send_alert(f"[Manifest Error] {e}")


def run_worker():
    """
    worker 메인 루프.

    Stage order (per cycle):
    1) scheduler(due timeframe 계산)
    2) ingest stage(수집/retention/activation/watermark)
    3) publish stage(export/predict + watermark gate)
    4) runtime metrics 기록 및 sleep/overrun 처리
    """
    scheduler_mode = WORKER_SCHEDULER_MODE
    if scheduler_mode not in VALID_WORKER_SCHEDULER_MODES:
        logger.warning(
            "[Scheduler] unsupported WORKER_SCHEDULER_MODE=%s, fallback to poll_loop.",
            scheduler_mode,
        )
        scheduler_mode = "poll_loop"

    worker_role = resolve_worker_execution_role(WORKER_EXECUTION_ROLE)
    run_ingest_stage = worker_role_runs_ingest(worker_role)
    run_publish_stage = worker_role_runs_publish(worker_role)
    publish_mode = resolve_worker_publish_mode(WORKER_PUBLISH_MODE)
    run_predict_stage = run_publish_stage and publish_mode_runs_predict(
        publish_mode
    )
    run_export_stage = run_publish_stage and publish_mode_runs_export(
        publish_mode
    )
    write_runtime_metrics = run_ingest_stage

    logger.info(
        f"[Pipeline Worker] Started. Target: {TARGET_COINS}, Timeframes: {TIMEFRAMES}, "
        f"SchedulerMode: {scheduler_mode}, WorkerRole: {worker_role}, "
        f"PublishMode: {publish_mode}"
    )

    client = InfluxDBClient(
        url=INFLUXDB_URL,
        token=INFLUXDB_TOKEN,
        org=INFLUXDB_ORG,
    )
    write_api = client.write_api(write_options=SYNCHRONOUS)
    query_api = client.query_api()
    delete_api = client.delete_api()
    ingest_state_store = IngestStateStore(INGEST_STATE_FILE)

    state = WorkerPersistentState(
        symbol_activation_entries=_load_symbol_activation(),
        ingest_watermarks=_load_watermark_entries(INGEST_WATERMARK_FILE),
        predict_watermarks=_load_watermark_entries(PREDICT_WATERMARK_FILE),
        export_watermarks=_load_watermark_entries(EXPORT_WATERMARK_FILE),
    )
    previous_disk_level: StorageGuardLevel | None = None
    last_retention_enforced_at: datetime | None = None
    activation_exchange = None
    if run_ingest_stage:
        activation_exchange = ccxt.binance()
        activation_exchange.enableRateLimit = True

    next_boundary_by_timeframe: dict[str, datetime] = {}
    if scheduler_mode == "boundary":
        next_boundary_by_timeframe = initialize_boundary_schedule(
            datetime.now(timezone.utc),
            TIMEFRAMES,
        )

    send_alert("Worker Started.")

    while True:
        cycle_started_at = datetime.now(timezone.utc)
        start_time = time.time()
        cycle_since_source_counts: dict[str, int] = {}
        cycle_detection_skip_counts: dict[str, int] = {}
        cycle_detection_run_counts: dict[str, int] = {}
        cycle_missed_boundary_count: int | None = None
        cycle_predict_gate_skip_counts: dict[str, int] = {}
        cycle_export_gate_skip_counts: dict[str, int] = {}

        if run_publish_stage and not run_ingest_stage:
            # publish 전용 프로세스는 ingest와 메모리를 공유하지 않는다.
            # 따라서 매 cycle 파일에서 최신 activation/watermark를 다시 읽어
            # 프로세스 간 eventual consistency를 맞춘다.
            state.symbol_activation_entries = _load_symbol_activation()
            state.ingest_watermarks = _load_watermark_entries(
                INGEST_WATERMARK_FILE
            )

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
                    if write_runtime_metrics:
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

            disk_level = StorageGuardLevel.NORMAL
            disk_usage_percent: float | None = None
            if run_ingest_stage:
                try:
                    disk_usage_percent = get_disk_usage_percent()
                    disk_level = _coerce_storage_guard_level(
                        resolve_disk_watermark_level(disk_usage_percent)
                    )
                    if previous_disk_level != disk_level:
                        msg = (
                            "[Storage Guard] "
                            f"usage={disk_usage_percent:.2f}% level={disk_level.value} "
                            f"(warn={DISK_WATERMARK_WARN_PERCENT}%, "
                            f"critical={DISK_WATERMARK_CRITICAL_PERCENT}%, "
                            f"block={DISK_WATERMARK_BLOCK_PERCENT}%)"
                        )
                        if disk_level == StorageGuardLevel.NORMAL:
                            logger.info(msg)
                        else:
                            logger.warning(msg)
                            send_alert(msg)
                    previous_disk_level = disk_level
                except OSError as e:
                    logger.error(
                        f"[Storage Guard] disk usage check failed: {e}"
                    )

            if (
                run_ingest_stage
                and "1m" in TIMEFRAMES
                and should_enforce_1m_retention(
                    last_retention_enforced_at,
                    cycle_now,
                )
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
                (
                    symbol_activation,
                    exchange_earliest,
                    activation_loaded,
                ) = _prepare_symbol_activation_for_cycle(
                    run_ingest_stage=run_ingest_stage,
                    query_api=query_api,
                    activation_exchange=activation_exchange,
                    symbol=symbol,
                    cycle_now=cycle_now,
                    state=state,
                )

                if (
                    symbol_activation.visibility
                    == SymbolVisibility.HIDDEN_BACKFILLING
                    and (run_ingest_stage or activation_loaded)
                ):
                    _remove_static_exports_for_symbol(
                        symbol,
                        TIMEFRAMES,
                        static_dir=STATIC_DIR,
                    )

                for timeframe in active_timeframes:
                    if run_ingest_stage:
                        (
                            should_continue_publish,
                            symbol_activation,
                        ) = _run_ingest_timeframe_step(
                            write_api=write_api,
                            query_api=query_api,
                            activation_exchange=activation_exchange,
                            ingest_state_store=ingest_state_store,
                            symbol=symbol,
                            timeframe=timeframe,
                            cycle_now=cycle_now,
                            scheduler_mode=scheduler_mode,
                            symbol_activation=symbol_activation,
                            exchange_earliest=exchange_earliest,
                            disk_level=disk_level,
                            disk_usage_percent=disk_usage_percent,
                            state=state,
                            cycle_since_source_counts=cycle_since_source_counts,
                            cycle_detection_skip_counts=cycle_detection_skip_counts,
                            cycle_detection_run_counts=cycle_detection_run_counts,
                        )
                        state.symbol_activation_entries[symbol] = (
                            symbol_activation
                        )
                        if not should_continue_publish:
                            continue

                    if not run_publish_stage:
                        continue

                    _run_publish_timeframe_step(
                        write_api=write_api,
                        query_api=query_api,
                        symbol=symbol,
                        timeframe=timeframe,
                        cycle_now=cycle_now,
                        symbol_activation=symbol_activation,
                        run_export_stage=run_export_stage,
                        run_predict_stage=run_predict_stage,
                        state=state,
                        cycle_export_gate_skip_counts=cycle_export_gate_skip_counts,
                        cycle_predict_gate_skip_counts=cycle_predict_gate_skip_counts,
                    )

            _persist_cycle_runtime_state(
                run_ingest_stage=run_ingest_stage,
                run_predict_stage=run_predict_stage,
                run_export_stage=run_export_stage,
                state=state,
            )

            if run_publish_stage:
                if cycle_predict_gate_skip_counts:
                    logger.info(
                        "[Publish Gate] predict skips=%s",
                        cycle_predict_gate_skip_counts,
                    )
                if cycle_export_gate_skip_counts:
                    logger.info(
                        "[Publish Gate] export skips=%s",
                        cycle_export_gate_skip_counts,
                    )

            elapsed = time.time() - start_time
            sleep_time = CYCLE_TARGET_SECONDS - elapsed
            overrun = sleep_time <= 0

            if write_runtime_metrics:
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
            error_msg = f"Worker Critical Error:\n{traceback.format_exc()}"
            logger.error(error_msg)
            send_alert(error_msg)
            elapsed = time.time() - start_time
            if write_runtime_metrics:
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
                        "Runtime metrics update failed after worker error: "
                        f"{metrics_error}"
                    )
            time.sleep(10)


if __name__ == "__main__":
    run_worker()
