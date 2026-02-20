import os
import time
from dataclasses import dataclass, replace
from datetime import datetime, timedelta, timezone
from pathlib import Path

import requests
from influxdb_client import InfluxDBClient

from utils.config import INGEST_TIMEFRAMES, PRIMARY_TIMEFRAME, TARGET_SYMBOLS
from utils.freshness import parse_utc_timestamp
from utils.logger import get_logger
from utils.prediction_status import (
    PredictionStatusSnapshot,
    evaluate_prediction_status,
)

logger = get_logger(__name__)

DISCORD_WEBHOOK_URL = os.getenv("DISCORD_WEBHOOK_URL", "")
STATIC_DATA_DIR = Path(os.getenv("STATIC_DATA_DIR", "/app/static_data"))
INFLUXDB_URL = os.getenv("INFLUXDB_URL")
INFLUXDB_TOKEN = os.getenv("INFLUXDB_TOKEN")
INFLUXDB_ORG = os.getenv("INFLUXDB_ORG")
INFLUXDB_BUCKET = os.getenv("INFLUXDB_BUCKET")


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
MONITOR_RE_ALERT_CYCLES = _parse_positive_int_env("MONITOR_RE_ALERT_CYCLES", 3)
MONITOR_ESCALATION_CYCLES = _parse_positive_int_env(
    "MONITOR_ESCALATION_CYCLES", 60
)

HEALTHY_STATUSES = {"fresh", "stale"}
ALERTABLE_UNHEALTHY_STATUSES = {"hard_stale", "corrupt", "missing"}


MonitorSnapshot = PredictionStatusSnapshot


@dataclass(frozen=True)
class MonitorAlertEvent:
    key: str
    symbol: str
    timeframe: str
    event: str
    previous_status: str | None
    current_snapshot: MonitorSnapshot
    cycles_in_status: int | None = None


def evaluate_symbol_timeframe(
    symbol: str,
    timeframe: str,
    now: datetime | None = None,
    static_dir: Path = STATIC_DATA_DIR,
    soft_thresholds: dict[str, timedelta] | None = None,
    hard_thresholds: dict[str, timedelta] | None = None,
) -> MonitorSnapshot:
    return evaluate_prediction_status(
        symbol=symbol,
        timeframe=timeframe,
        now=now,
        static_dir=static_dir,
        soft_thresholds=soft_thresholds,
        hard_thresholds=hard_thresholds,
    )


def detect_alert_event(
    previous_status: str | None, current_status: str
) -> str | None:
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


def update_status_cycle_counter(
    counters: dict[str, dict[str, str | int]],
    key: str,
    current_status: str,
) -> int:
    """
    key별로 동일 상태가 몇 사이클 연속됐는지 누적한다.

    상태가 바뀌면 카운터를 1로 리셋하고,
    동일 상태가 유지되면 카운터를 +1 한다.
    """
    previous = counters.get(key)
    if isinstance(previous, dict) and previous.get("status") == current_status:
        raw_cycles = previous.get("cycles", 0)
        try:
            cycles = int(raw_cycles) + 1
        except (TypeError, ValueError):
            cycles = 1
    else:
        cycles = 1

    counters[key] = {"status": current_status, "cycles": cycles}
    return cycles


def detect_realert_event(
    current_status: str, cycles_in_status: int
) -> str | None:
    """
    상태가 바뀌지 않고 오래 지속될 때 주기적으로 재알림한다.

    정책:
    - hard_stale/corrupt/missing: 3사이클마다 재알림
    - stale(soft): 즉시 알림은 없지만 3사이클 이상 지속 시 재알림
    """
    if cycles_in_status < MONITOR_RE_ALERT_CYCLES:
        return None
    if cycles_in_status % MONITOR_RE_ALERT_CYCLES != 0:
        return None

    if current_status in ALERTABLE_UNHEALTHY_STATUSES:
        return f"{current_status}_repeat"
    if current_status == "stale":
        return "soft_stale_repeat"
    return None


def detect_escalation_event(
    current_status: str, cycles_in_status: int
) -> str | None:
    """
    장기 지속 상태를 운영 승격(escalation) 이벤트로 표준화한다.

    정책:
    - 기본은 MONITOR_ESCALATION_CYCLES(기본 60) 주기
    - hard_stale/corrupt/missing: `<status>_escalated`
    - stale(soft): `soft_stale_escalated`
    """
    if cycles_in_status < MONITOR_ESCALATION_CYCLES:
        return None
    if cycles_in_status % MONITOR_ESCALATION_CYCLES != 0:
        return None

    if current_status in ALERTABLE_UNHEALTHY_STATUSES:
        return f"{current_status}_escalated"
    if current_status == "stale":
        return "soft_stale_escalated"
    return None


def _extract_latest_timestamp_from_result(result) -> datetime | None:
    """
    Flux query 결과에서 전역 latest `_time`를 추출한다.

    Why:
    - `last()`가 series별 table을 반환할 수 있어 단일 table 가정을 피해야 한다.
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
        logger.error(f"[Monitor] Influx latest ohlcv query failed: {e}")
        return None
    return _extract_latest_timestamp_from_result(result)


def get_latest_ohlcv_timestamp(
    query_api, symbol: str, timeframe: str
) -> datetime | None:
    """
    Return the latest OHLCV timestamp for a given symbol+timeframe.

    NOTE:
    Compatibility:
    - PRIMARY_TIMEFRAME는 legacy(no-timeframe-tag) row fallback을 허용한다.
    """
    if query_api is None or not INFLUXDB_BUCKET:
        return None

    scoped_query = f"""
    from(bucket: "{INFLUXDB_BUCKET}")
      |> range(start: -30d)
      |> filter(fn: (r) => r["_measurement"] == "ohlcv")
      |> filter(fn: (r) => r["symbol"] == "{symbol}")
      |> filter(fn: (r) => r["timeframe"] == "{timeframe}")
      |> last(column: "_time")
    """
    latest_ts = _query_latest_ohlcv_timestamp(query_api, scoped_query)
    if latest_ts is not None:
        return latest_ts

    if timeframe != PRIMARY_TIMEFRAME:
        return None

    legacy_query = f"""
    from(bucket: "{INFLUXDB_BUCKET}")
      |> range(start: -30d)
      |> filter(fn: (r) => r["_measurement"] == "ohlcv")
      |> filter(fn: (r) => r["symbol"] == "{symbol}")
      |> filter(fn: (r) => not exists r["timeframe"])
      |> last(column: "_time")
    """
    return _query_latest_ohlcv_timestamp(query_api, legacy_query)


def apply_influx_json_consistency(
    snapshot: MonitorSnapshot, latest_ohlcv_ts: datetime | None
) -> MonitorSnapshot:
    """
    Influx(SoT)와 JSON(파생 산출물) 간 시각 갭을 추가 검증한다.

    기본 정책:
    1) JSON 자체가 이미 missing/corrupt면 그 결과를 우선한다.
    2) Influx 정보가 없으면 오탐을 피하기 위해 JSON 판정을 유지한다.
    3) 갭이 hard_limit을 넘는 경우에만 hard_stale로 승격한다.
    """
    # Influx 설정이 없거나, 쿼리 실패/결과 없음 (Influx 장애를 서비스 장애로 오탐 가능)
    # 따라서, JSON 기준 판정을 존중하여 return.
    if latest_ohlcv_ts is None:
        return snapshot
    # 이미 JSON에서 판정된 상태라면, Influx 기준으로 판정하지 않음.
    if snapshot.status in {"missing", "corrupt"}:
        return snapshot
    # updated_at: JSON이 언제 생성 되었는 지 없고,
    # hard_limit_minutes: 허용 가능한 최대 갭이 없으면,
    # Influx vs. JSON 간 갭 규칙을 적용할 수 없음.
    if snapshot.updated_at is None or snapshot.hard_limit_minutes is None:
        return snapshot

    # 파싱 실패 => timestamp 형식 오류/문자열 오염 등.
    updated_at = parse_utc_timestamp(snapshot.updated_at)
    if updated_at is None:
        return replace(
            snapshot,
            status="corrupt",
            detail="influx_json_mismatch: invalid snapshot updated_at",
        )

    # 앞/뒤 관계보다 "절대 시각 차이"가 중요하므로 absolute gap으로 계산.
    gap = updated_at - latest_ohlcv_ts
    if gap < timedelta(0):
        gap = -gap

    # JSON 존중. 아마 status = healthy
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


def run_monitor_cycle(
    state: dict[str, MonitorSnapshot],
    status_counters: dict[str, dict[str, str | int]] | None = None,
    now: datetime | None = None,
    symbols: list[str] | None = None,
    timeframes: list[str] | None = None,
    static_dir: Path = STATIC_DATA_DIR,
    soft_thresholds: dict[str, timedelta] | None = None,
    hard_thresholds: dict[str, timedelta] | None = None,
    query_api=None,
) -> list[MonitorAlertEvent]:
    resolved_now = now or datetime.now(timezone.utc)
    resolved_symbols = symbols or TARGET_SYMBOLS
    resolved_timeframes = timeframes or INGEST_TIMEFRAMES
    resolved_status_counters = (
        status_counters if status_counters is not None else {}
    )
    events: list[MonitorAlertEvent] = []

    for symbol in resolved_symbols:
        for timeframe in resolved_timeframes:
            key = f"{symbol}|{timeframe}"
            latest_ohlcv_ts = get_latest_ohlcv_timestamp(
                query_api, symbol, timeframe
            )
            base_snapshot = evaluate_symbol_timeframe(
                symbol=symbol,
                timeframe=timeframe,
                now=resolved_now,
                static_dir=static_dir,
                soft_thresholds=soft_thresholds,
                hard_thresholds=hard_thresholds,
            )
            snapshot = apply_influx_json_consistency(
                base_snapshot, latest_ohlcv_ts
            )
            # JSON 단독 판정과 최종 판정이 달라졌다면, 운영자 추적을 위해 명시 로그를 남긴다.
            if snapshot.status != base_snapshot.status:
                logger.warning(
                    "[Monitor] Consistency override: "
                    f"{symbol} {timeframe} {base_snapshot.status}->{snapshot.status} "
                    f"detail={snapshot.detail}"
                )
            previous_status = state.get(key).status if key in state else None
            event = detect_alert_event(previous_status, snapshot.status)
            cycles_in_status = update_status_cycle_counter(
                resolved_status_counters, key, snapshot.status
            )
            # 상태전이 알림이 없으면 escalation -> repeat 순서로 판단한다.
            if event is None:
                event = detect_escalation_event(
                    snapshot.status, cycles_in_status
                )
            if event is None:
                event = detect_realert_event(snapshot.status, cycles_in_status)
            if event:
                events.append(
                    MonitorAlertEvent(
                        key=key,
                        symbol=symbol,
                        timeframe=timeframe,
                        event=event,
                        previous_status=previous_status,
                        current_snapshot=snapshot,
                        cycles_in_status=cycles_in_status,
                    )
                )

            state[key] = snapshot
            logger.info(
                f"[Monitor] {symbol} {timeframe} "
                f"status={snapshot.status} cycles={cycles_in_status} "
                f"detail={snapshot.detail}"
            )

    return events


def send_discord_alert(event: MonitorAlertEvent) -> None:
    runbook_line = (
        "\naction=runbook: docs/RUNBOOK_STALE_ESCALATION.md"
        if event.event.endswith("_escalated")
        else ""
    )
    cycles_line = (
        f"\ncycles_in_status={event.cycles_in_status}"
        if event.cycles_in_status is not None
        else ""
    )
    message = (
        f"[{event.event.upper()}] {event.symbol} {event.timeframe}\n"
        f"prev={event.previous_status} -> now={event.current_snapshot.status}\n"
        f"detail={event.current_snapshot.detail}\n"
        f"updated_at={event.current_snapshot.updated_at}\n"
        f"age_minutes={event.current_snapshot.age_minutes}"
        f"{cycles_line}"
        f"{runbook_line}"
    )

    if not DISCORD_WEBHOOK_URL:
        logger.info(f"[Alert Ignored] {message}")
        return

    try:
        payload = {
            "content": f"**Coin Predict Monitor Alert**\n```{message}```"
        }
        response = requests.post(DISCORD_WEBHOOK_URL, json=payload, timeout=5)
        response.raise_for_status()
    except Exception as e:
        logger.error(f"Failed to send monitor alert: {e}")


def run_monitor() -> None:
    logger.info(
        f"[Status Monitor] started. symbols={TARGET_SYMBOLS}, timeframes={INGEST_TIMEFRAMES}, poll={MONITOR_POLL_SECONDS}s"
    )

    influx_client = None
    query_api = None
    if INFLUXDB_URL and INFLUXDB_TOKEN and INFLUXDB_ORG and INFLUXDB_BUCKET:
        try:
            influx_client = InfluxDBClient(
                url=INFLUXDB_URL, token=INFLUXDB_TOKEN, org=INFLUXDB_ORG
            )
            query_api = influx_client.query_api()
            logger.info("[Status Monitor] Influx consistency check enabled.")
        except Exception as e:
            logger.error(
                f"[Status Monitor] Failed to initialize Influx client: {e}"
            )

    state: dict[str, MonitorSnapshot] = {}
    status_counters: dict[str, dict[str, str | int]] = {}
    try:
        while True:
            cycle_start = time.time()
            try:
                events = run_monitor_cycle(
                    state,
                    status_counters=status_counters,
                    query_api=query_api,
                )
                for event in events:
                    send_discord_alert(event)
            except Exception as e:
                logger.error(f"Status monitor cycle error: {e}")

            elapsed = time.time() - cycle_start
            sleep_for = max(1.0, MONITOR_POLL_SECONDS - elapsed)
            time.sleep(sleep_for)
    finally:
        if influx_client is not None:
            influx_client.close()


if __name__ == "__main__":
    run_monitor()
