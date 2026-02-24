"""
Ingest domain logic.

Why this module exists:
- `scripts.pipeline_worker`는 orchestration에 집중하고,
  실제 ingest 계산/판정은 여기로 모아 변경 영향 범위를 축소한다.
- 모든 timeframe을 거래소 direct fetch로 수집해 ingest 경로를 단순화한다.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import ccxt
import pandas as pd
from utils.pipeline_contracts import (
    DetectionGateDecision,
    DetectionGateReason,
    SymbolActivationSnapshot,
    SymbolActivationState,
    SymbolVisibility,
)


def count_ohlcv_rows(ctx, query_api, *, symbol: str, timeframe: str) -> int:
    """
    symbol+timeframe의 OHLCV 총 행 수를 반환한다.

    Called from:
    - `scripts.pipeline_worker.count_ohlcv_rows` (D-010 min sample gate)

    Why:
    - 예측 실행 전 최소 샘플 수 충족 여부를 판단하기 위한 전제 데이터.
    """
    query = f"""
    from(bucket: "{ctx.INFLUXDB_BUCKET}")
      |> range(start: 0)
      |> filter(fn: (r) => r["_measurement"] == "ohlcv")
      |> filter(fn: (r) => r["symbol"] == "{symbol}")
      |> filter(fn: (r) => r["timeframe"] == "{timeframe}")
      |> filter(fn: (r) => r["_field"] == "close")
      |> count()
    """
    try:
        tables = query_api.query(query)
    except Exception as e:
        ctx.logger.error(f"[{symbol} {timeframe}] sample count query failed: {e}")
        return 0
    for table in tables:
        for record in table.records:
            try:
                return int(record.get_value())
            except (TypeError, ValueError):
                return 0
    return 0


def fetch_ohlcv_paginated(
    ctx,
    exchange,
    symbol: str,
    timeframe: str,
    since_ms: int,
    until_ms: int,
) -> tuple[pd.DataFrame, int]:
    """
    거래소 OHLCV를 cursor 기반으로 페이지 단위 수집한다.

    Called from:
    - `fetch_and_save`
    - `refill_detected_gaps`

    Why:
    - 거래소 API limit 제약을 안전하게 우회하면서 중복/역순 데이터를 정리한다.
    """
    fetch_limit = 1000
    timeframe_ms = exchange.parse_timeframe(timeframe) * 1000
    cursor = int(since_ms)
    page_count = 0
    chunks: list[pd.DataFrame] = []

    while cursor <= until_ms:
        ohlcv = exchange.fetch_ohlcv(symbol, timeframe, since=cursor, limit=fetch_limit)
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


def detect_gaps_from_ms_timestamps(
    ctx,
    timestamps_ms: list[int],
    timeframe: str,
):
    """
    타임스탬프 목록에서 candle gap 구간을 탐지한다.

    Called from:
    - `fetch_and_save` (초기 수집 후 / refill 후 재검증)

    Why:
    - 수집 누락을 즉시 감지해 silent hole을 줄이기 위함이다.
    """
    candle_opens = [
        datetime.fromtimestamp(int(ts) / 1000, tz=timezone.utc) for ts in timestamps_ms
    ]
    return ctx.detect_timeframe_gaps(candle_opens, timeframe)


def refill_detected_gaps(
    ctx,
    exchange,
    symbol: str,
    timeframe: str,
    source_df: pd.DataFrame,
    gaps,
    last_closed_ms: int,
) -> tuple[pd.DataFrame, int]:
    """
    감지된 gap 구간을 재조회해 source_df를 보강한다.

    Called from:
    - `fetch_and_save` (gap 발견 시)

    Why:
    - 경고만 남기지 않고 자동 보정해 운영자 개입 없이 회복률을 높인다.
    """
    if not gaps:
        return source_df, 0

    refill_since_ms = int(gaps[0].start_open.timestamp() * 1000)
    refill_df, refill_pages = fetch_ohlcv_paginated(
        ctx,
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


def fetch_and_save(
    ctx,
    write_api,
    symbol: str,
    since_ts,
    timeframe: str,
) -> tuple[datetime | None, str]:
    """
    base timeframe ingest(거래소 조회 -> closed filter -> gap 보정 -> DB 저장)를 수행한다.

    Called from:
    - `scripts.pipeline_worker.run_ingest_step` (base timeframe)

    Why:
    - 미완료 candle 제외와 gap 보정을 기본 동작으로 강제해 데이터 무결성을 우선한다.
    """
    exchange = ccxt.binance()
    exchange.enableRateLimit = True

    if isinstance(since_ts, datetime):
        since_ms = int(since_ts.timestamp() * 1000)
    else:
        since_ms = int(since_ts)

    try:
        now = datetime.now(timezone.utc)
        now_ms = int(now.timestamp() * 1000)
        last_closed_open = ctx.last_closed_candle_open(now, timeframe)
        last_closed_ms = int(last_closed_open.timestamp() * 1000)

        df, page_count = fetch_ohlcv_paginated(
            ctx,
            exchange=exchange,
            symbol=symbol,
            timeframe=timeframe,
            since_ms=since_ms,
            until_ms=now_ms,
        )
        if df.empty:
            ctx.logger.info(f"[{symbol} {timeframe}] 새로운 데이터 없음.")
            return None, "no_data"

        before_filter = len(df)
        df = df[df["timestamp"] <= last_closed_ms]
        dropped = before_filter - len(df)
        if dropped > 0:
            ctx.logger.info(
                f"[{symbol} {timeframe}] 미완료 캔들 {dropped}개 제외 "
                f"(last_closed_open={last_closed_open.strftime('%Y-%m-%dT%H:%M:%SZ')})"
            )
        if df.empty:
            ctx.logger.info(
                f"[{symbol} {timeframe}] 저장 가능한 closed candle 없음 "
                f"(last_closed_open={last_closed_open.strftime('%Y-%m-%dT%H:%M:%SZ')})."
            )
            return None, "no_data"

        gaps = detect_gaps_from_ms_timestamps(
            ctx, timestamps_ms=df["timestamp"].tolist(), timeframe=timeframe
        )
        if gaps:
            total_missing = sum(gap.missing_count for gap in gaps)
            first_gap = gaps[0]
            ctx.logger.warning(
                f"[{symbol} {timeframe}] Gap 감지: windows={len(gaps)}, missing={total_missing}, "
                f"first={first_gap.start_open.strftime('%Y-%m-%dT%H:%M:%SZ')}~"
                f"{first_gap.end_open.strftime('%Y-%m-%dT%H:%M:%SZ')}"
            )
            df, refill_pages = refill_detected_gaps(
                ctx,
                exchange=exchange,
                symbol=symbol,
                timeframe=timeframe,
                source_df=df,
                gaps=gaps,
                last_closed_ms=last_closed_ms,
            )
            if refill_pages > 0:
                ctx.logger.info(
                    f"[{symbol} {timeframe}] Gap refill 시도 완료 (pages={refill_pages})"
                )

            remaining_gaps = detect_gaps_from_ms_timestamps(
                ctx,
                timestamps_ms=df["timestamp"].tolist(),
                timeframe=timeframe,
            )
            if remaining_gaps:
                remaining_missing = sum(gap.missing_count for gap in remaining_gaps)
                ctx.logger.warning(
                    f"[{symbol} {timeframe}] Gap 잔존: windows={len(remaining_gaps)}, missing={remaining_missing}"
                )
            else:
                ctx.logger.info(f"[{symbol} {timeframe}] Gap refill 완료.")

        df["timestamp"] = pd.to_datetime(df["timestamp"], unit="ms").dt.tz_localize(
            "UTC"
        )
        df.set_index("timestamp", inplace=True)
        df["symbol"] = symbol
        df["timeframe"] = timeframe

        write_api.write(
            bucket=ctx.INFLUXDB_BUCKET,
            org=ctx.INFLUXDB_ORG,
            record=df,
            data_frame_measurement_name="ohlcv",
            data_frame_tag_columns=["symbol", "timeframe"],
        )
        ctx.logger.info(
            f"[{symbol} {timeframe}] {len(df)}개 봉 저장 완료 "
            f"(pages={page_count}, Last={df.index[-1]})"
        )
        latest_saved_at = df.index[-1].to_pydatetime().astimezone(timezone.utc)
        return latest_saved_at, "saved"

    except Exception as e:
        ctx.logger.error(f"[{symbol} {timeframe}] 수집 실패: {e}")
        return None, "failed"


def resolve_ingest_since(
    ctx,
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

    Called from:
    - `scripts.pipeline_worker.run_worker` (각 symbol/timeframe ingest 직전)

    우선순위:
    1) DB last timestamp (SoT)
    2) lookback bootstrap

    Why:
    - cursor/state가 깨져도 DB SoT를 우선해 잘못된 기준점 전파를 막고,
      필요 시 rebootstrap으로 자동 복구한다.

    Source code examples:
    - "db_last": DB latest를 그대로 이어받는 정상 증분 수집
    - "bootstrap_exchange_earliest": full-fill 대상 TF의 최초 전체 백필 시작
    - "underfilled_rebootstrap": lookback row 부족으로 재부트스트랩
    - "blocked_storage_guard": 저장소 가드로 초기 백필 차단
    """
    resolved_now = now or datetime.now(timezone.utc)
    if (
        enforce_full_backfill
        and timeframe == ctx.SYMBOL_ACTIVATION_SOURCE_TIMEFRAME
        and bootstrap_since is not None
    ):
        # hidden_backfilling 상태에서는 canonical 1h를 거래소 earliest부터 강제 수집한다.
        return bootstrap_since, "full_backfill_exchange_earliest"

    if force_rebootstrap:
        if ctx.should_block_initial_backfill(
            disk_level=disk_level,
            timeframe=timeframe,
            state_since=None,
            last_time=None,
        ):
            return None, "blocked_storage_guard"

        # full-fill TF는 lookback 대신 exchange earliest부터 재수집해
        # historical gap을 근본적으로 메운다.
        if timeframe in ctx.DB_FULL_FILL_TIMEFRAMES and bootstrap_since is not None:
            return bootstrap_since, "underfilled_rebootstrap_exchange_earliest"

        lookback_days = ctx._lookback_days_for_timeframe(timeframe)
        # 비full-fill TF는 최근 lookback 윈도우만 다시 수집한다.
        return (
            resolved_now - timedelta(days=lookback_days),
            "underfilled_rebootstrap",
        )

    if last_time is not None:
        if state_since is not None and state_since > last_time:
            ctx.logger.warning(
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
        ctx.logger.warning(
            f"[{symbol} {timeframe}] state cursor exists but DB has no last timestamp. "
            "Rebootstrapping from lookback window."
        )

    if ctx.should_block_initial_backfill(
        disk_level=disk_level,
        timeframe=timeframe,
        state_since=guard_state_since,
        last_time=last_time,
    ):
        return None, "blocked_storage_guard"

    if timeframe in ctx.DB_FULL_FILL_TIMEFRAMES and bootstrap_since is not None:
        # full-fill 대상 TF는 exchange earliest를 우선해 lookback truncation을 방지한다.
        if source == "state_drift_rebootstrap":
            return (
                bootstrap_since,
                "state_drift_rebootstrap_exchange_earliest",
            )
        return bootstrap_since, "bootstrap_exchange_earliest"

    lookback_days = ctx._lookback_days_for_timeframe(timeframe)
    return resolved_now - timedelta(days=lookback_days), source


def minimum_required_lookback_rows(
    ctx,
    timeframe: str,
    lookback_days: int,
) -> int | None:
    """
    lookback 구간의 최소 허용 row 수를 계산한다.

    Called from:
    - `scripts.pipeline_worker.run_worker` underfill guard 판단.

    Why:
    - coverage underfill을 조기에 감지해 불완전 bootstrap 상태를 자동 교정한다.
    """
    # 현재 운영 기준에서 coverage 보정은 1h canonical에만 적용한다.
    if timeframe != "1h":
        return None
    expected = lookback_days * 24
    if expected <= 0:
        return None
    return max(1, int(expected * ctx.LOOKBACK_MIN_ROWS_RATIO))


def get_lookback_close_count(
    ctx,
    query_api,
    symbol: str,
    timeframe: str,
    lookback_days: int,
) -> int | None:
    """
    lookback 구간 close row 수를 조회한다.

    Called from:
    - `scripts.pipeline_worker.run_worker` underfill guard 판단.

    Why:
    - 단일 latest timestamp만으로는 coverage 충분성을 보장할 수 없기 때문이다.
    """
    query = f"""
    from(bucket: "{ctx.INFLUXDB_BUCKET}")
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
        ctx.logger.error(f"[{symbol} {timeframe}] lookback count query failed: {e}")
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


def query_last_timestamp(query_api, query: str) -> datetime | None:
    """
    last timestamp 쿼리 실행 유틸.

    Called from:
    - `get_last_timestamp`
    """
    result = query_api.query(query=query)
    if len(result) == 0 or len(result[0].records) == 0:
        return None
    return result[0].records[0].get_time()


def query_first_timestamp(query_api, query: str) -> datetime | None:
    """
    first timestamp 쿼리 실행 유틸.

    Called from:
    - `get_first_timestamp`
    """
    result = query_api.query(query=query)
    if len(result) == 0 or len(result[0].records) == 0:
        return None
    return result[0].records[0].get_time()


def get_first_timestamp(
    ctx,
    query_api,
    symbol: str,
    timeframe: str,
) -> datetime | None:
    """
    DB earliest candle open을 조회한다(legacy fallback 포함).

    Called from:
    - `build_symbol_activation_entry`

    Why:
    - full-backfill readiness를 판단하려면 coverage 시작점이 필요하다.
    """
    query = f"""
    from(bucket: "{ctx.INFLUXDB_BUCKET}")
      |> range(start: 0)
      |> filter(fn: (r) => r["_measurement"] == "ohlcv")
      |> filter(fn: (r) => r["symbol"] == "{symbol}")
      |> filter(fn: (r) => r["timeframe"] == "{timeframe}")
      |> first(column: "_time")
    """
    legacy_query = f"""
    from(bucket: "{ctx.INFLUXDB_BUCKET}")
      |> range(start: 0)
      |> filter(fn: (r) => r["_measurement"] == "ohlcv")
      |> filter(fn: (r) => r["symbol"] == "{symbol}")
      |> filter(fn: (r) => not exists r["timeframe"])
      |> first(column: "_time")
    """

    try:
        first_time = ctx._query_first_timestamp(query_api, query)
        if first_time is None and timeframe == ctx.PRIMARY_TIMEFRAME:
            first_time = ctx._query_first_timestamp(query_api, legacy_query)
        return first_time
    except Exception as e:
        ctx.logger.error(f"[{symbol} {timeframe}] DB earliest 조회 중 에러: {e}")
        return None


def get_last_timestamp(
    ctx,
    query_api,
    symbol,
    timeframe,
    *,
    full_range: bool = False,
) -> datetime | None:
    """
    DB latest candle open을 조회한다(legacy fallback 포함).

    Called from:
    - `resolve_ingest_since`
    - `evaluate_detection_gate`
    - `build_symbol_activation_entry`

    Why:
    - ingest/publish gate 기준이 되는 최신 닫힌 봉 시각을 일관되게 제공한다.
    """
    lookback_days = ctx._lookback_days_for_timeframe(timeframe)
    range_start = "0" if full_range else f"-{lookback_days}d"
    query = f"""
    from(bucket: "{ctx.INFLUXDB_BUCKET}")
      |> range(start: {range_start})
      |> filter(fn: (r) => r["_measurement"] == "ohlcv")
      |> filter(fn: (r) => r["symbol"] == "{symbol}")
      |> filter(fn: (r) => r["timeframe"] == "{timeframe}")
      |> last(column: "_time")
    """
    legacy_query = f"""
    from(bucket: "{ctx.INFLUXDB_BUCKET}")
      |> range(start: {range_start})
      |> filter(fn: (r) => r["_measurement"] == "ohlcv")
      |> filter(fn: (r) => r["symbol"] == "{symbol}")
      |> filter(fn: (r) => not exists r["timeframe"])
      |> last(column: "_time")
    """

    try:
        last_time = ctx._query_last_timestamp(query_api, query)
        if last_time is None and timeframe == ctx.PRIMARY_TIMEFRAME:
            last_time = ctx._query_last_timestamp(query_api, legacy_query)
        if last_time is not None:
            return last_time
    except Exception as e:
        ctx.logger.error(
            f"[{symbol} {timeframe}] DB 조회 중 에러 (아마 데이터 없음): {e}"
        )

    return None


def get_exchange_earliest_closed_timestamp(
    ctx,
    exchange,
    symbol: str,
    timeframe: str,
    *,
    now: datetime | None = None,
) -> datetime | None:
    """
    거래소가 제공하는 earliest *closed* candle open을 조회한다.

    Called from:
    - `scripts.pipeline_worker.run_worker` symbol activation 계산.

    Why:
    - 상장일 메타 대신 실제 조회 가능한 earliest candle을 기준으로
      full-backfill 판정을 수행하기 위함이다.
    """
    try:
        rows = exchange.fetch_ohlcv(symbol, timeframe, since=0, limit=1)
    except Exception as e:
        ctx.logger.warning(
            f"[{symbol} {timeframe}] failed to fetch exchange earliest candle: {e}"
        )
        return None

    if not rows:
        return None

    try:
        first_open = datetime.fromtimestamp(int(rows[0][0]) / 1000, tz=timezone.utc)
    except (TypeError, ValueError):
        return None

    resolved_now = now or datetime.now(timezone.utc)
    last_closed = ctx.last_closed_candle_open(resolved_now, timeframe)
    if first_open > last_closed:
        return None
    return first_open


def get_exchange_latest_closed_timestamp(
    ctx,
    exchange,
    symbol: str,
    timeframe: str,
    *,
    now: datetime | None = None,
) -> datetime | None:
    """
    거래소 latest *closed* candle open을 조회한다.

    Called from:
    - `evaluate_detection_gate`

    Why:
    - open candle을 포함하면 detection gate가 중복 실행/오판을 유발할 수 있다.
    """
    resolved_now = now or datetime.now(timezone.utc)
    expected_latest_closed = ctx.last_closed_candle_open(resolved_now, timeframe)
    try:
        rows = exchange.fetch_ohlcv(symbol, timeframe, limit=3)
    except Exception as e:
        ctx.logger.warning(
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
    ctx,
    query_api,
    detection_exchange,
    *,
    symbol: str,
    timeframe: str,
    now: datetime,
    last_saved: datetime | None = None,
) -> DetectionGateDecision:
    """
    boundary 시점에 실제 cycle 실행 필요 여부를 판단한다.

    Called from:
    - `scripts.pipeline_worker.run_worker` (scheduler_mode=boundary)

    Why:
    - boundary + detection 하이브리드 정책에서 불필요 cycle을 줄이면서
      경계 정합성을 유지하기 위한 핵심 게이트다.
    """
    latest_closed = ctx.get_exchange_latest_closed_timestamp(
        detection_exchange,
        symbol,
        timeframe,
        now=now,
    )
    if latest_closed is None:
        return DetectionGateDecision(
            should_run=True,
            reason=DetectionGateReason.DETECTION_UNAVAILABLE_FALLBACK_RUN,
        )

    reference_last = (
        last_saved
        if last_saved is not None
        else ctx.get_last_timestamp(query_api, symbol, timeframe)
    )
    if reference_last is not None and reference_last >= latest_closed:
        return DetectionGateDecision(
            should_run=False,
            reason=DetectionGateReason.NO_NEW_CLOSED_CANDLE,
        )
    return DetectionGateDecision(
        should_run=True,
        reason=DetectionGateReason.NEW_CLOSED_CANDLE,
    )


def build_symbol_activation_entry(
    ctx,
    *,
    query_api,
    symbol: str,
    now: datetime,
    exchange_earliest: datetime | None,
    existing_entry: SymbolActivationSnapshot | dict | None = None,
) -> SymbolActivationSnapshot:
    """
    symbol activation 상태(registered/backfilling/ready_for_serving)를 계산한다.

    Called from:
    - `scripts.pipeline_worker.run_worker` 각 심볼 cycle.

    Why:
    - full-backfill 완료 전 심볼 비노출 정책을 코드 레벨에서 강제하기 위함이다.
    """
    canonical_tf = ctx.SYMBOL_ACTIVATION_SOURCE_TIMEFRAME
    db_first = ctx.get_first_timestamp(query_api, symbol, canonical_tf)
    db_last = ctx.get_last_timestamp(query_api, symbol, canonical_tf, full_range=True)

    if isinstance(existing_entry, SymbolActivationSnapshot):
        prev_entry = existing_entry
    else:
        prev_entry = SymbolActivationSnapshot.from_payload(
            symbol=symbol,
            payload=existing_entry if isinstance(existing_entry, dict) else {},
            fallback_now=now,
        )

    prev_ready = prev_entry.is_full_backfilled
    tolerance = timedelta(hours=max(0, ctx.FULL_BACKFILL_TOLERANCE_HOURS))

    if prev_ready and db_first is not None:
        state = SymbolActivationState.READY_FOR_SERVING
        visibility = SymbolVisibility.VISIBLE
        is_full_backfilled = True
    elif db_first is None:
        state = SymbolActivationState.REGISTERED
        visibility = SymbolVisibility.HIDDEN_BACKFILLING
        is_full_backfilled = False
    elif exchange_earliest is None:
        state = SymbolActivationState.BACKFILLING
        visibility = SymbolVisibility.HIDDEN_BACKFILLING
        is_full_backfilled = False
    else:
        starts_covered = db_first <= (exchange_earliest + tolerance)
        is_full_backfilled = starts_covered
        if starts_covered:
            state = SymbolActivationState.READY_FOR_SERVING
            visibility = SymbolVisibility.VISIBLE
        else:
            state = SymbolActivationState.BACKFILLING
            visibility = SymbolVisibility.HIDDEN_BACKFILLING

    ready_at = prev_entry.ready_at
    if is_full_backfilled and ready_at is None:
        ready_at = now

    return SymbolActivationSnapshot(
        symbol=symbol,
        state=state,
        visibility=visibility,
        is_full_backfilled=is_full_backfilled,
        coverage_start_at=db_first,
        coverage_end_at=db_last,
        exchange_earliest_at=exchange_earliest,
        ready_at=ready_at,
        updated_at=now,
    )
