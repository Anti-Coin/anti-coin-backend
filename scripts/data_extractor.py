"""
ML 모델 학습 데이터를 InfluxDB에서 추출하여 정적 스냅샷(예: Parquet) 파일로 저장한다.

Why this module exists:
- ML 학습 과정과 InfluxDB 쿼리 부하를 분리하여 Oracle Free Tier의 OOM(Out of Memory) 문제를 예방한다.
- 데이터 추출을 Chunk 단위로 분할하여 안정성을 확보한다.
"""

from __future__ import annotations

import os
from datetime import datetime, timezone, timedelta
from pathlib import Path
from influxdb_client import InfluxDBClient
import pandas as pd

from scripts.worker_config import (
    INFLUXDB_URL,
    INFLUXDB_TOKEN,
    INFLUXDB_ORG,
    INFLUXDB_BUCKET,
    STATIC_DIR,
)

SNAPSHOTS_DIR = STATIC_DIR / "snapshots"
# 기본 추출 단위: 30일 (OOM 방지 설정)
CHUNK_DAYS = int(os.getenv("EXTRACT_CHUNK_DAYS", "30"))


def _get_influx_client() -> InfluxDBClient:
    return InfluxDBClient(
        url=INFLUXDB_URL,
        token=INFLUXDB_TOKEN,
        org=INFLUXDB_ORG,
        timeout=60000,
    )


def _query_chunk(
    query_api, symbol: str, timeframe: str, start: datetime, stop: datetime
) -> pd.DataFrame:
    """Queries a specific chunk between start and stop times."""
    query = f"""
    from(bucket: "{INFLUXDB_BUCKET}")
      |> range(start: {int(start.timestamp())}, stop: {int(stop.timestamp())})
      |> filter(fn: (r) => r["_measurement"] == "ohlcv")
      |> filter(fn: (r) => r["symbol"] == "{symbol}")
      |> filter(fn: (r) => r["timeframe"] == "{timeframe}")
      |> pivot(rowKey:["_time"], columnKey: ["_field"], valueColumn: "_value")
      |> sort(columns: ["_time"], desc: false)
    """
    result = query_api.query_data_frame(query)

    if isinstance(result, list):
        frames = [f for f in result if isinstance(f, pd.DataFrame) and not f.empty]
        if not frames:
            return pd.DataFrame()
        df = pd.concat(frames, ignore_index=True)
    else:
        df = result

    if not isinstance(df, pd.DataFrame) or df.empty:
        return pd.DataFrame()

    required = {"_time", "open", "high", "low", "close", "volume"}
    if not required.issubset(df.columns):
        return pd.DataFrame()

    df.rename(columns={"_time": "timestamp"}, inplace=True)
    df["timestamp"] = pd.to_datetime(df["timestamp"], utc=True)
    return df[["timestamp", "open", "high", "low", "close", "volume"]]


def extract_ohlcv_to_parquet(
    symbol: str,
    timeframe: str,
    lookback_limit: int,
    client: InfluxDBClient | None = None,
    dest_path: Path | None = None,
) -> Path:
    """
    주어진 symbol과 timeframe에 대해 최근 `lookback_limit` 캔들을 추출한다.

    Why:
    - 매 학습마다 InfluxDB 전체를 스캔하지 않고, 정적 Parquet 파일로 저장하여 메모리/연산 제약을 극복한다.
    - OOM을 피하기 위해 조회 기간을 근사치로 계산한 뒤, 분할된 청크 단위 쿼리로 안전하게 데이터를 적재한다.
    """
    if dest_path is None:
        SNAPSHOTS_DIR.mkdir(parents=True, exist_ok=True)
        safe_symbol = symbol.replace("/", "_")
        dest_path = SNAPSHOTS_DIR / f"train_data_{safe_symbol}_{timeframe}.parquet"

    own_client = False
    if client is None:
        client = _get_influx_client()
        own_client = True

    try:
        query_api = client.query_api()

        # Calculate time range for the extraction based on lookback limit
        now = datetime.now(timezone.utc)

        # Approximate distance back in time
        if timeframe == "1m":
            tdelta = timedelta(minutes=lookback_limit)
        elif timeframe == "1h":
            tdelta = timedelta(hours=lookback_limit)
        elif timeframe == "4h":
            tdelta = timedelta(hours=lookback_limit * 4)
        elif timeframe == "1d":
            tdelta = timedelta(days=lookback_limit)
        elif timeframe == "1w":
            tdelta = timedelta(weeks=lookback_limit)
        elif timeframe == "1M":
            tdelta = timedelta(days=lookback_limit * 30)
        else:
            tdelta = timedelta(days=lookback_limit)  # fallback

        # We fetch slightly more time to account for weekends/gaps when needed
        extended_tdelta = tdelta * 1.5
        start_time = now - extended_tdelta

        chunks = []
        current_start = start_time

        while current_start < now:
            current_stop = current_start + timedelta(days=CHUNK_DAYS)
            if current_stop > now:
                current_stop = now

            chunk_df = _query_chunk(
                query_api, symbol, timeframe, current_start, current_stop
            )
            if not chunk_df.empty:
                chunks.append(chunk_df)

            current_start = current_stop

        if not chunks:
            # Create an empty dataframe with correct structure
            final_df = pd.DataFrame(
                columns=["timestamp", "open", "high", "low", "close", "volume"]
            )
            final_df.to_parquet(dest_path, index=False)
            return dest_path

        final_df = pd.concat(chunks, ignore_index=True)
        final_df.drop_duplicates(subset=["timestamp"], keep="last", inplace=True)
        final_df.sort_values(by="timestamp", inplace=True)

        # Trim to exact lookback_limit requested
        if len(final_df) > lookback_limit:
            final_df = final_df.tail(lookback_limit).reset_index(drop=True)

        final_df.to_parquet(dest_path, index=False)
        return dest_path

    finally:
        if own_client:
            client.close()
