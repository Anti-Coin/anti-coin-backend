"""
Storage/disk guard and retention enforcement.

Why this module exists:
- pipeline_worker.py에서 디스크/저장소 관련 가드와 retention 로직을 분리해
  오케스트레이션 코드의 인지 부하를 줄인다.
- 이 함수들은 순수 계산이거나 외부 API(delete_api)만 의존하므로
  오케스트레이션과 느슨한 결합이다.
"""

from __future__ import annotations

import shutil
from datetime import datetime, timedelta, timezone
from pathlib import Path

from utils.logger import get_logger
from utils.pipeline_contracts import StorageGuardLevel
from scripts.worker_config import (
    DISK_USAGE_PATH,
    DISK_WATERMARK_BLOCK_PERCENT,
    DISK_WATERMARK_CRITICAL_PERCENT,
    DISK_WATERMARK_WARN_PERCENT,
    INFLUXDB_BUCKET,
    INFLUXDB_ORG,
    RETENTION_1M_DEFAULT_DAYS,
    RETENTION_1M_MAX_DAYS,
    RETENTION_ENFORCE_INTERVAL_SECONDS,
)

logger = get_logger(__name__)


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
    cutoff = (resolved_now - timedelta(days=effective_days)).replace(microsecond=0)
    epoch = datetime(1970, 1, 1, tzinfo=timezone.utc)

    for symbol in symbols:
        predicate = f'_measurement="ohlcv" AND symbol="{symbol}" AND timeframe="1m"'
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


def coerce_storage_guard_level(raw_level: str) -> StorageGuardLevel:
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
