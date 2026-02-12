import ccxt
import pandas as pd
from influxdb_client import InfluxDBClient
from influxdb_client.client.write_api import SYNCHRONOUS
from prophet.serialize import model_from_json
import os
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
import requests
import traceback
from utils.logger import get_logger
from utils.config import TARGET_SYMBOLS, PRIMARY_TIMEFRAME
from utils.file_io import atomic_write_json
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
TIMEFRAME = PRIMARY_TIMEFRAME
LOOKBACK_DAYS = 30  # 과거 30일치 데이터 유지


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


def get_last_timestamp(query_api, symbol):
    """
    InfluxDB에서 해당 코인의 가장 마지막 데이터 시간(Timestamp)을 조회
    """
    query = f"""
    from(bucket: "{INFLUXDB_BUCKET}")
      |> range(start: -{LOOKBACK_DAYS}d)
      |> filter(fn: (r) => r["_measurement"] == "ohlcv")
      |> filter(fn: (r) => r["symbol"] == "{symbol}")
      |> last(column: "_time")
    """
    try:
        result = query_api.query(query=query)
        if len(result) > 0 and len(result[0].records) > 0:
            last_time = result[0].records[0].get_time()
            # InfluxDB 시간은 UTC timezone이 포함됨.
            return last_time
    except Exception as e:
        logger.error(f"[{symbol}] DB 조회 중 에러 (아마 데이터 없음): {e}")

    return None


def save_history_to_json(df, symbol):
    """
    과거 데이터(1h) 정적 파일 생성
    TODO: 지금은 단순하게 1시간 봉에 대해서만 정적 파일을 생성하고 있는데, (predict도 마찬가지)
    추후에 확장할 것.
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
            "type": "history_1h",
        }

        safe_symbol = symbol.replace("/", "_")
        file_path = STATIC_DIR / f"history_{safe_symbol}.json"
        atomic_write_json(file_path, json_output)

        logger.info(f"[{symbol}] 정적 파일 생성 완료: {file_path}")
    except Exception as e:
        logger.error(f"[{symbol}] 정적 파일 생성 실패: {e}")


def fetch_and_save(write_api, symbol, since_ts):
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
        last_closed_open = last_closed_candle_open(now, TIMEFRAME)
        last_closed_ms = int(last_closed_open.timestamp() * 1000)

        df, page_count = _fetch_ohlcv_paginated(
            exchange=exchange,
            symbol=symbol,
            timeframe=TIMEFRAME,
            since_ms=since_ms,
            until_ms=now_ms,
        )
        if df.empty:
            logger.info(f"[{symbol}] 새로운 데이터 없음.")
            return

        # 미완료 캔들은 저장하지 않는다.
        before_filter = len(df)
        df = df[df["timestamp"] <= last_closed_ms]
        dropped = before_filter - len(df)
        if dropped > 0:
            logger.info(
                f"[{symbol}] 미완료 캔들 {dropped}개 제외 (last_closed_open={last_closed_open.strftime('%Y-%m-%dT%H:%M:%SZ')})"
            )
        if df.empty:
            logger.info(
                f"[{symbol}] 저장 가능한 closed candle 없음 (last_closed_open={last_closed_open.strftime('%Y-%m-%dT%H:%M:%SZ')})."
            )
            return

        gaps = _detect_gaps_from_ms_timestamps(
            timestamps_ms=df["timestamp"].tolist(), timeframe=TIMEFRAME
        )
        if gaps:
            total_missing = sum(gap.missing_count for gap in gaps)
            first_gap = gaps[0]
            logger.warning(
                f"[{symbol}] Gap 감지: windows={len(gaps)}, missing={total_missing}, "
                f"first={first_gap.start_open.strftime('%Y-%m-%dT%H:%M:%SZ')}~"
                f"{first_gap.end_open.strftime('%Y-%m-%dT%H:%M:%SZ')}"
            )
            df, refill_pages = _refill_detected_gaps(
                exchange=exchange,
                symbol=symbol,
                timeframe=TIMEFRAME,
                source_df=df,
                gaps=gaps,
                last_closed_ms=last_closed_ms,
            )
            if refill_pages > 0:
                logger.info(
                    f"[{symbol}] Gap refill 시도 완료 (pages={refill_pages})"
                )

            remaining_gaps = _detect_gaps_from_ms_timestamps(
                timestamps_ms=df["timestamp"].tolist(),
                timeframe=TIMEFRAME,
            )
            if remaining_gaps:
                remaining_missing = sum(
                    gap.missing_count for gap in remaining_gaps
                )
                logger.warning(
                    f"[{symbol}] Gap 잔존: windows={len(remaining_gaps)}, missing={remaining_missing}"
                )
            else:
                logger.info(f"[{symbol}] Gap refill 완료.")

        df["timestamp"] = pd.to_datetime(
            df["timestamp"], unit="ms"
        ).dt.tz_localize("UTC")
        df.set_index("timestamp", inplace=True)

        # 태그 추가
        df["symbol"] = symbol

        # 저장
        write_api.write(
            bucket=INFLUXDB_BUCKET,
            org=INFLUXDB_ORG,
            record=df,
            data_frame_measurement_name="ohlcv",
            data_frame_tag_columns=["symbol"],
        )
        logger.info(
            f"[{symbol}] {len(df)}개 봉 저장 완료 (pages={page_count}, Last={df.index[-1]})"
        )

        # TODO: SSG 파일 생성을 DB 조회 후 덮어쓰기로 구현?

    except Exception as e:
        logger.error(f"[{symbol}] 수집 실패: {e}")


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


def _detect_gaps_from_ms_timestamps(
    timestamps_ms: list[int], timeframe: str
):
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


def run_prediction_and_save(write_api, symbol):
    """모델 로드 -> 예측 -> 저장"""
    # 모델 로드
    model_file = MODELS_DIR / f"model_{symbol.replace('/', '_')}.json"
    if not model_file.exists():
        logger.warning(f"[{symbol}] 모델 없음")
        return

    try:
        with open(model_file, "r") as fin:
            model = model_from_json(fin.read())

        # 예측 시작 시점을 "다음 캔들 경계"로 정렬한다.
        # 예: 10:37 + 1h -> 11:00 시작
        now = datetime.now(timezone.utc)
        prediction_start = next_timeframe_boundary(now, TIMEFRAME)
        prediction_freq = timeframe_to_pandas_freq(TIMEFRAME)
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
            logger.warning(f"[{symbol}] 예측 범위 생성 실패.")
            return

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
            "updated_at": now.strftime("%Y-%m-%dT%H:%M:%SZ"),  # 생성 시점 기록
            "forecast": export_data.to_dict(orient="records"),
        }

        # 파일 저장 (덮어쓰기)
        safe_symbol = symbol.replace("/", "_")
        file_path = STATIC_DIR / f"prediction_{safe_symbol}.json"
        atomic_write_json(file_path, json_output, indent=2)

        logger.info(
            f"[{symbol}] SSG 파일 생성 완료: {file_path} (start={prediction_start.strftime('%Y-%m-%dT%H:%M:%SZ')}, freq={TIMEFRAME})"
        )

        # 저장(DB)
        next_forecast["ds"] = pd.to_datetime(next_forecast["ds"]).dt.tz_localize(
            "UTC"
        )  # 불필요한 연산 같기는 한데,,, 방어용???
        next_forecast = next_forecast[["ds", "yhat", "yhat_lower", "yhat_upper"]]
        next_forecast.rename(columns={"ds": "timestamp"}, inplace=True)
        next_forecast.set_index(
            "timestamp", inplace=True
        )  # InfluxDB는 index가 timestamp
        next_forecast["symbol"] = symbol

        write_api.write(
            bucket=INFLUXDB_BUCKET,
            org=INFLUXDB_ORG,
            record=next_forecast,
            data_frame_measurement_name="prediction",
            data_frame_tag_columns=["symbol"],
        )
        logger.info(f"[{symbol}] {len(next_forecast)}개 예측 저장 완료")

    except Exception as e:
        logger.error(f"[{symbol}] 예측 에러: {e}")


def update_full_history_file(query_api, symbol):
    """DB에서 최근 30일치 데이터를 긁어와서 history json 파일 갱신"""
    query = f"""
    from(bucket: "{INFLUXDB_BUCKET}")
      |> range(start: -30d)
      |> filter(fn: (r) => r["_measurement"] == "ohlcv")
      |> filter(fn: (r) => r["symbol"] == "{symbol}")
      |> pivot(rowKey:["_time"], columnKey: ["_field"], valueColumn: "_value")
      |> sort(columns: ["_time"], desc: false)
    """
    try:
        df = query_api.query_data_frame(query)
        if not df.empty:
            df.rename(columns={"_time": "timestamp"}, inplace=True)  # UTC Aware
            df.set_index("timestamp", inplace=True)
            save_history_to_json(df, symbol)
    except Exception as e:
        logger.error(f"[{symbol}] History 갱신 중 에러: {e}")


def run_worker():
    logger.info(
        f"[Pipeline Worker] Started. Target: {TARGET_COINS}, Timeframe: {TIMEFRAME}"
    )

    client = InfluxDBClient(
        url=INFLUXDB_URL, token=INFLUXDB_TOKEN, org=INFLUXDB_ORG
    )
    write_api = client.write_api(write_options=SYNCHRONOUS)
    query_api = client.query_api()

    send_alert("Worker Started.")

    while True:
        try:
            start_time = time.time()
            logger.info(
                f"\n[Cycle] 작업 시작: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
            )

            for symbol in TARGET_COINS:
                # DB에서 마지막 데이터 시간 확인
                last_time = get_last_timestamp(query_api, symbol)

                # 시작 시간 결정 (Since)
                if last_time:
                    # 마지막 데이터가 있으면, 그 시간부터 다시 가져옴 (덮어쓰기 업데이트)
                    since = last_time
                else:
                    # 데이터가 아예 없으면 30일 전부터
                    since = datetime.now(timezone.utc) - timedelta(
                        days=LOOKBACK_DAYS
                    )
                    logger.info(
                        f"[{symbol}] 초기 데이터 수집 시작 (30일 전부터)"
                    )

                # 수집
                fetch_and_save(write_api, symbol, since)

                # History 파일 갱신
                update_full_history_file(query_api, symbol)

                # 예측
                run_prediction_and_save(write_api, symbol)

            # Cycle Overrun 감지 및 주기 보정
            elapsed = time.time() - start_time
            sleep_time = 60 - elapsed

            if sleep_time > 0:
                logger.info(
                    f"Cycle finished in {elapsed:.2f}s. Sleeping for {sleep_time:.2f}s..."
                )
                time.sleep(sleep_time)
            else:
                warning_msg = (
                    f"[Warning] Cycle Overrun! Took {elapsed:.2f}s (Limit: 60s)"
                )
                send_alert(warning_msg)

        except Exception as e:
            # Worker가 죽지 않도록 잡지만, 운영자에게는 알림
            error_msg = f"Worker Critical Error:\n{traceback.format_exc()}"
            logger.error(error_msg)
            send_alert(error_msg)
            time.sleep(10)  # 에러 루프 방지용 대기


if __name__ == "__main__":
    run_worker()
