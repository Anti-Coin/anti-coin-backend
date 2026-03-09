from __future__ import annotations

from dataclasses import replace
from datetime import datetime, timedelta, timezone

from utils.freshness import parse_utc_timestamp
from utils.logger import get_logger
from utils.prediction_status import PredictionStatusSnapshot

logger = get_logger(__name__)


def _extract_latest_timestamp_from_result(result) -> datetime | None:
    """
    Flux query 결과에서 전역 latest `_time`를 추출한다.

    Why:
    - `last()` 결과가 series별 table로 분리될 수 있어
      단일 table 가정을 피해야 한다.
    """
    latest_ts: datetime | None = None
    for table in result:
        for record in getattr(table, "records", []):
            ts = record.get_time()
            if ts is None:
                continue
            if ts.tzinfo is None:
                ts = ts.replace(tzinfo=timezone.utc)
            else:
                ts = ts.astimezone(timezone.utc)
            if latest_ts is None or ts > latest_ts:
                latest_ts = ts
    return latest_ts


def _query_latest_ohlcv_timestamp(query_api, query: str) -> datetime | None:
    """
    주어진 Flux query를 실행해 latest `_time`를 반환한다.
    """
    try:
        result = query_api.query(query=query)
    except Exception as e:
        logger.error(f"[Status Consistency] Influx latest ohlcv query failed: {e}")
        return None
    return _extract_latest_timestamp_from_result(result)


def get_latest_ohlcv_timestamp(
    query_api,
    symbol: str,
    timeframe: str,
    influx_bucket: str | None,
    primary_timeframe: str,
) -> datetime | None:
    """
    symbol+timeframe의 latest OHLCV timestamp를 조회한다.
    """
    if query_api is None or not influx_bucket:
        return None

    scoped_query = f"""
    from(bucket: "{influx_bucket}")
      |> range(start: -30d)
      |> filter(fn: (r) => r["_measurement"] == "ohlcv")
      |> filter(fn: (r) => r["symbol"] == "{symbol}")
      |> filter(fn: (r) => r["timeframe"] == "{timeframe}")
      |> last(column: "_time")
    """
    return _query_latest_ohlcv_timestamp(query_api, scoped_query)


def apply_influx_json_consistency(
    snapshot: PredictionStatusSnapshot, latest_ohlcv_ts: datetime | None
) -> PredictionStatusSnapshot:
    """
    Influx(SoT)와 JSON(파생 산출물) 간 시각 갭을 추가 검증한다.

    기본 정책:
    1) JSON 자체가 이미 missing/corrupt면 그 결과를 우선한다.
    2) Influx 정보가 없으면 JSON 판정을 유지한다.
    3) 갭이 hard_limit을 넘는 경우에만 hard_stale로 승격한다.
    """
    if latest_ohlcv_ts is None:
        return snapshot
    if snapshot.status in {"missing", "corrupt"}:
        return snapshot
    if snapshot.updated_at is None or snapshot.hard_limit_minutes is None:
        return snapshot

    updated_at = parse_utc_timestamp(snapshot.updated_at)
    if updated_at is None:
        return replace(
            snapshot,
            status="corrupt",
            detail="influx_json_mismatch: invalid snapshot updated_at",
        )

    gap = updated_at - latest_ohlcv_ts
    if gap < timedelta(0):
        gap = -gap

    max_gap = timedelta(minutes=snapshot.hard_limit_minutes)
    if gap <= max_gap:
        return snapshot

    gap_minutes = round(gap.total_seconds() / 60, 2)
    return replace(
        snapshot,
        status="hard_stale",
        detail=(
            "influx_json_mismatch: "
            f"ohlcv_last={latest_ohlcv_ts.strftime('%Y-%m-%dT%H:%M:%SZ')}, "
            f"prediction_updated_at={snapshot.updated_at}, "
            f"gap_minutes={gap_minutes}"
        ),
    )
