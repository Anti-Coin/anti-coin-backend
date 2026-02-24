from datetime import datetime, timezone, timedelta
from pathlib import Path

import pandas as pd
import pytest

from scripts.data_extractor import extract_ohlcv_to_parquet, _query_chunk


class FakeQueryAPI:
    def __init__(self, dataframes: list[pd.DataFrame] = None):
        self.dataframes = dataframes or []
        self.queries = []
        self.call_count = 0

    def query_data_frame(self, query):
        self.queries.append(query)
        if self.call_count < len(self.dataframes):
            df = self.dataframes[self.call_count]
            self.call_count += 1
            return df
        return pd.DataFrame()


class FakeInfluxClient:
    def __init__(self, query_api):
        self._query_api = query_api
        self.closed = False

    def query_api(self):
        return self._query_api

    def close(self):
        self.closed = True


def test_extract_ohlcv_chunks_and_limits(tmp_path, monkeypatch):
    # 여러 청크로 분할 조회되도록 CHUNK_DAYS를 작게 강제 설정한다.
    monkeypatch.setattr("scripts.data_extractor.CHUNK_DAYS", 10)

    # lookback_limit 50 검증 목적.
    # 3번의 쿼리 시뮬레이션:
    # Query 1: 20 rows
    # Query 2: 40 rows
    # Query 3: 0 rows (빈 결과 시뮬레이션)

    # 테스트용 행 데이터 생성기
    now = datetime(2026, 2, 21, 12, 0, tzinfo=timezone.utc)

    def make_df(start_idx, count):
        rows = []
        for i in range(count):
            rows.append(
                {
                    "_time": now - timedelta(days=(100 - (start_idx + i))),
                    "open": 100.0 + i,
                    "high": 105.0 + i,
                    "low": 95.0 + i,
                    "close": 102.0 + i,
                    "volume": 1000.0 + i,
                }
            )
        return pd.DataFrame(rows)

    q1 = make_df(0, 20)
    q2 = make_df(20, 40)
    q3 = pd.DataFrame()  # 빈 결과 시뮬레이션

    fake_query = FakeQueryAPI([q1, q2, q3])
    fake_client = FakeInfluxClient(fake_query)

    out_path = tmp_path / "train_data_BTC_USDT_1d.parquet"

    result_path = extract_ohlcv_to_parquet(
        symbol="BTC/USDT",
        timeframe="1d",
        lookback_limit=50,
        client=fake_client,
        dest_path=out_path,
    )

    assert result_path.exists()

    df = pd.read_parquet(result_path)
    # 총 60개 행을 수집했지만, lookback_limit이 50이므로 정확히 50개 캔들로 잘려야 한다.
    assert len(df) == 50
    assert "timestamp" in df.columns
    assert "close" in df.columns

    # 다중 쿼리(청크 분할)가 올바로 수행되었는지 검증한다.
    assert fake_query.call_count >= 2


def test_extract_ohlcv_empty_result(tmp_path):
    fake_query = FakeQueryAPI([])
    fake_client = FakeInfluxClient(fake_query)
    out_path = tmp_path / "empty.parquet"

    extract_ohlcv_to_parquet(
        symbol="BTC/USDT",
        timeframe="1d",
        lookback_limit=50,
        client=fake_client,
        dest_path=out_path,
    )

    df = pd.read_parquet(out_path)
    assert len(df) == 0
    assert list(df.columns) == ["timestamp", "open", "high", "low", "close", "volume"]
