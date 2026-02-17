import json
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

import pandas as pd

from scripts.pipeline_worker import (
    _detect_gaps_from_ms_timestamps,
    _fetch_ohlcv_paginated,
    _lookback_days_for_timeframe,
    _minimum_required_lookback_rows,
    _refill_detected_gaps,
    append_runtime_cycle_metrics,
    build_runtime_manifest,
    downsample_ohlcv_frame,
    enforce_1m_retention,
    get_first_timestamp,
    get_disk_usage_percent,
    get_last_timestamp,
    prediction_enabled_for_timeframe,
    resolve_ingest_since,
    resolve_disk_watermark_level,
    run_downsample_and_save,
    run_prediction_and_save,
    save_history_to_json,
    should_block_initial_backfill,
    should_enforce_1m_retention,
    upsert_prediction_health,
    write_runtime_manifest,
)


def _to_ms(dt: datetime) -> int:
    return int(dt.timestamp() * 1000)


class FakeExchange:
    def __init__(self, candles: list[list[float]]):
        self._candles = sorted(candles, key=lambda row: row[0])

    def parse_timeframe(self, timeframe: str) -> int:
        if timeframe == "1h":
            return 60 * 60
        raise ValueError("unsupported timeframe for test")

    def fetch_ohlcv(
        self, symbol: str, timeframe: str, since: int, limit: int
    ) -> list[list[float]]:
        candidates = [row for row in self._candles if row[0] >= since]
        return candidates[:limit]


class FakeDeleteAPI:
    def __init__(self):
        self.calls = []

    def delete(self, **kwargs):
        self.calls.append(kwargs)


class FakeQueryAPI:
    def __init__(self, dataframe):
        self._dataframe = dataframe

    def query_data_frame(self, query: str):
        return self._dataframe


class FakeWriteAPI:
    def __init__(self):
        self.calls = []

    def write(self, **kwargs):
        self.calls.append(kwargs)


def test_fetch_ohlcv_paginated_respects_until_ms():
    base = datetime(2026, 2, 12, 0, 0, tzinfo=timezone.utc)
    candles = [
        [_to_ms(base + timedelta(hours=offset)), 1.0, 1.0, 1.0, 1.0, 1.0]
        for offset in range(4)
    ]
    exchange = FakeExchange(candles)

    loaded, pages = _fetch_ohlcv_paginated(
        exchange=exchange,
        symbol="BTC/USDT",
        timeframe="1h",
        since_ms=_to_ms(base),
        until_ms=_to_ms(base + timedelta(hours=2)),
    )

    assert pages == 1
    assert loaded["timestamp"].tolist() == [
        _to_ms(base),
        _to_ms(base + timedelta(hours=1)),
        _to_ms(base + timedelta(hours=2)),
    ]


def test_refill_detected_gaps_recovers_missing_candle():
    base = datetime(2026, 2, 12, 0, 0, tzinfo=timezone.utc)
    full_candles = [
        [_to_ms(base + timedelta(hours=offset)), 1.0, 1.0, 1.0, 1.0, 1.0]
        for offset in range(4)
    ]
    exchange = FakeExchange(full_candles)

    source_df = pd.DataFrame(
        [
            full_candles[0],
            full_candles[1],
            full_candles[3],
        ],
        columns=["timestamp", "open", "high", "low", "close", "volume"],
    )
    gaps = _detect_gaps_from_ms_timestamps(
        source_df["timestamp"].tolist(), timeframe="1h"
    )

    merged, refill_pages = _refill_detected_gaps(
        exchange=exchange,
        symbol="BTC/USDT",
        timeframe="1h",
        source_df=source_df,
        gaps=gaps,
        last_closed_ms=_to_ms(base + timedelta(hours=3)),
    )

    assert refill_pages == 1
    assert merged["timestamp"].tolist() == [
        _to_ms(base),
        _to_ms(base + timedelta(hours=1)),
        _to_ms(base + timedelta(hours=2)),
        _to_ms(base + timedelta(hours=3)),
    ]


def test_upsert_prediction_health_tracks_failure_and_recovery(tmp_path):
    health_path = tmp_path / "prediction_health.json"

    first, was_degraded, is_degraded = upsert_prediction_health(
        "BTC/USDT",
        "1h",
        prediction_ok=False,
        error="model_missing",
        path=health_path,
    )
    assert was_degraded is False
    assert is_degraded is True
    assert first["consecutive_failures"] == 1
    assert first["last_success_at"] is None
    assert first["last_error"] == "model_missing"

    second, was_degraded, is_degraded = upsert_prediction_health(
        "BTC/USDT",
        "1h",
        prediction_ok=False,
        error="model_missing",
        path=health_path,
    )
    assert was_degraded is True
    assert is_degraded is True
    assert second["consecutive_failures"] == 2

    third, was_degraded, is_degraded = upsert_prediction_health(
        "BTC/USDT",
        "1h",
        prediction_ok=True,
        path=health_path,
    )
    assert was_degraded is True
    assert is_degraded is False
    assert third["consecutive_failures"] == 0
    assert third["last_success_at"] is not None
    assert third["last_failure_at"] is not None


def test_prediction_enabled_for_timeframe_respects_disabled_set(monkeypatch):
    monkeypatch.setattr(
        "scripts.pipeline_worker.PREDICTION_DISABLED_TIMEFRAMES",
        {"1m", "5m"},
    )

    assert prediction_enabled_for_timeframe("1m") is False
    assert prediction_enabled_for_timeframe("1h") is True


def test_run_prediction_and_save_skips_disabled_timeframe(monkeypatch):
    monkeypatch.setattr(
        "scripts.pipeline_worker.PREDICTION_DISABLED_TIMEFRAMES",
        {"1m"},
    )

    result, error = run_prediction_and_save(
        write_api=None,
        symbol="BTC/USDT",
        timeframe="1m",
    )
    assert result == "skipped"
    assert error is None


def test_save_history_to_json_writes_timeframe_aware_files(
    tmp_path, monkeypatch
):
    monkeypatch.setattr("scripts.pipeline_worker.STATIC_DIR", tmp_path)

    base = datetime(2026, 2, 12, 0, 0, tzinfo=timezone.utc)
    df = pd.DataFrame(
        [
            {
                "timestamp": base,
                "open": 1.0,
                "high": 2.0,
                "low": 0.5,
                "close": 1.5,
                "volume": 10.0,
            }
        ]
    ).set_index("timestamp")

    save_history_to_json(df, "BTC/USDT", "4h")

    canonical_path = tmp_path / "history_BTC_USDT_4h.json"
    legacy_path = tmp_path / "history_BTC_USDT.json"
    assert canonical_path.exists()
    assert legacy_path.exists()

    payload = json.loads(canonical_path.read_text())
    assert payload["symbol"] == "BTC/USDT"
    assert payload["timeframe"] == "4h"
    assert payload["type"] == "history_4h"


def test_build_runtime_manifest_merges_freshness_and_health(tmp_path):
    symbol = "BTC/USDT"
    timeframe = "1h"
    safe_symbol = symbol.replace("/", "_")
    now = datetime(2026, 2, 13, 12, 0, tzinfo=timezone.utc)

    history_path = tmp_path / f"history_{safe_symbol}_{timeframe}.json"
    history_path.write_text(
        json.dumps(
            {
                "symbol": symbol,
                "timeframe": timeframe,
                "updated_at": "2026-02-13T11:15:00Z",
                "data": [],
            }
        )
    )
    prediction_path = tmp_path / f"prediction_{safe_symbol}_{timeframe}.json"
    prediction_path.write_text(
        json.dumps(
            {
                "symbol": symbol,
                "timeframe": timeframe,
                "updated_at": "2026-02-13T11:30:00Z",
                "forecast": [],
            }
        )
    )
    health_path = tmp_path / "prediction_health.json"
    health_path.write_text(
        json.dumps(
            {
                "version": 1,
                "updated_at": "2026-02-13T11:31:00Z",
                "entries": {
                    "BTC/USDT|1h": {
                        "degraded": True,
                        "last_success_at": "2026-02-13T11:00:00Z",
                        "last_failure_at": "2026-02-13T11:29:00Z",
                        "consecutive_failures": 2,
                    }
                },
            }
        )
    )

    manifest = build_runtime_manifest(
        [symbol],
        [timeframe],
        now=now,
        static_dir=tmp_path,
        prediction_health_path=health_path,
    )

    assert manifest["version"] == 1
    assert manifest["summary"]["entry_count"] == 1
    assert manifest["summary"]["status_counts"]["fresh"] == 1
    assert manifest["summary"]["degraded_count"] == 1

    entry = manifest["entries"][0]
    assert entry["key"] == "BTC/USDT|1h"
    assert entry["history"]["updated_at"] == "2026-02-13T11:15:00Z"
    assert entry["prediction"]["status"] == "fresh"
    assert entry["prediction"]["updated_at"] == "2026-02-13T11:30:00Z"
    assert entry["degraded"] is True
    assert entry["prediction_failure_count"] == 2
    assert entry["serve_allowed"] is True
    assert entry["visibility"] == "visible"
    assert entry["symbol_state"] == "ready_for_serving"
    assert entry["is_full_backfilled"] is True


def test_write_runtime_manifest_writes_manifest_file(tmp_path):
    symbol = "BTC/USDT"
    timeframe = "1h"
    manifest_path = tmp_path / "manifest.json"

    write_runtime_manifest(
        [symbol],
        [timeframe],
        now=datetime(2026, 2, 13, 12, 0, tzinfo=timezone.utc),
        static_dir=tmp_path,
        prediction_health_path=tmp_path / "prediction_health.json",
        path=manifest_path,
    )

    payload = json.loads(manifest_path.read_text())
    assert payload["version"] == 1
    assert payload["summary"]["entry_count"] == 1
    assert payload["summary"]["status_counts"]["missing"] == 1
    assert payload["summary"]["visible_symbol_count"] == 1
    assert payload["summary"]["hidden_symbol_count"] == 0
    assert payload["entries"][0]["serve_allowed"] is False


def test_append_runtime_cycle_metrics_writes_summary(tmp_path):
    metrics_path = tmp_path / "runtime_metrics.json"
    base = datetime(2026, 2, 13, 12, 0, tzinfo=timezone.utc)

    append_runtime_cycle_metrics(
        started_at=base,
        elapsed_seconds=12.4,
        sleep_seconds=47.6,
        overrun=False,
        cycle_result="ok",
        path=metrics_path,
        target_cycle_seconds=60,
        window_size=10,
    )
    append_runtime_cycle_metrics(
        started_at=base + timedelta(minutes=1),
        elapsed_seconds=70.0,
        sleep_seconds=0.0,
        overrun=True,
        cycle_result="failed",
        error="worker_error",
        path=metrics_path,
        target_cycle_seconds=60,
        window_size=10,
    )

    payload = json.loads(metrics_path.read_text())
    assert payload["target_cycle_seconds"] == 60
    assert payload["window_size"] == 10
    assert payload["boundary_tracking"]["missed_boundary_supported"] is False
    assert payload["summary"]["samples"] == 2
    assert payload["summary"]["success_count"] == 1
    assert payload["summary"]["failure_count"] == 1
    assert payload["summary"]["overrun_count"] == 1
    assert payload["summary"]["p95_elapsed_seconds"] == 70.0
    assert payload["summary"]["missed_boundary_count"] is None
    assert payload["recent_cycles"][1]["error"] == "worker_error"


def test_append_runtime_cycle_metrics_applies_window_limit(tmp_path):
    metrics_path = tmp_path / "runtime_metrics.json"
    base = datetime(2026, 2, 13, 12, 0, tzinfo=timezone.utc)

    append_runtime_cycle_metrics(
        started_at=base,
        elapsed_seconds=10.0,
        sleep_seconds=50.0,
        overrun=False,
        cycle_result="ok",
        path=metrics_path,
        window_size=2,
    )
    append_runtime_cycle_metrics(
        started_at=base + timedelta(minutes=1),
        elapsed_seconds=11.0,
        sleep_seconds=49.0,
        overrun=False,
        cycle_result="ok",
        path=metrics_path,
        window_size=2,
    )
    append_runtime_cycle_metrics(
        started_at=base + timedelta(minutes=2),
        elapsed_seconds=12.0,
        sleep_seconds=48.0,
        overrun=False,
        cycle_result="ok",
        path=metrics_path,
        window_size=2,
    )

    payload = json.loads(metrics_path.read_text())
    assert len(payload["recent_cycles"]) == 2
    assert payload["recent_cycles"][0]["started_at"] == "2026-02-13T12:01:00Z"
    assert payload["recent_cycles"][1]["started_at"] == "2026-02-13T12:02:00Z"
    assert payload["summary"]["samples"] == 2


def test_lookback_days_for_timeframe_uses_1m_policy():
    assert _lookback_days_for_timeframe("1m") == 14
    assert _lookback_days_for_timeframe("1h") == 30


def test_resolve_disk_watermark_level():
    assert resolve_disk_watermark_level(60.0) == "normal"
    assert resolve_disk_watermark_level(70.0) == "warn"
    assert resolve_disk_watermark_level(85.0) == "critical"
    assert resolve_disk_watermark_level(90.0) == "block"


def test_get_disk_usage_percent_uses_shutil_result(monkeypatch):
    monkeypatch.setattr(
        "scripts.pipeline_worker.shutil.disk_usage",
        lambda _: SimpleNamespace(total=100, used=50, free=50),
    )
    assert get_disk_usage_percent() == 50.0


def test_should_enforce_1m_retention_interval():
    now = datetime(2026, 2, 13, 12, 0, tzinfo=timezone.utc)
    assert should_enforce_1m_retention(None, now) is True
    assert (
        should_enforce_1m_retention(now - timedelta(minutes=59), now) is False
    )
    assert should_enforce_1m_retention(now - timedelta(hours=1), now) is True


def test_should_block_initial_backfill_only_for_1m_block_mode():
    assert (
        should_block_initial_backfill(
            disk_level="block",
            timeframe="1m",
            state_since=None,
            last_time=None,
        )
        is True
    )
    assert (
        should_block_initial_backfill(
            disk_level="critical",
            timeframe="1m",
            state_since=None,
            last_time=None,
        )
        is False
    )
    assert (
        should_block_initial_backfill(
            disk_level="block",
            timeframe="1h",
            state_since=None,
            last_time=None,
        )
        is False
    )


def test_resolve_ingest_since_prefers_db_last_over_state_cursor():
    now = datetime(2026, 2, 13, 12, 0, tzinfo=timezone.utc)
    state_since = datetime(2026, 2, 13, 10, 0, tzinfo=timezone.utc)
    db_last = datetime(2026, 2, 13, 9, 0, tzinfo=timezone.utc)

    since, source = resolve_ingest_since(
        symbol="BTC/USDT",
        timeframe="1h",
        state_since=state_since,
        last_time=db_last,
        disk_level="normal",
        now=now,
    )

    assert since == db_last
    assert source == "db_last"


def test_resolve_ingest_since_rebootstraps_when_db_is_empty():
    now = datetime(2026, 2, 13, 12, 0, tzinfo=timezone.utc)
    state_since = datetime(2026, 2, 13, 11, 0, tzinfo=timezone.utc)

    since, source = resolve_ingest_since(
        symbol="BTC/USDT",
        timeframe="1h",
        state_since=state_since,
        last_time=None,
        disk_level="normal",
        now=now,
    )

    assert source == "state_drift_rebootstrap"
    assert since == datetime(2026, 1, 14, 12, 0, tzinfo=timezone.utc)


def test_resolve_ingest_since_blocks_1m_drift_backfill_on_block_level():
    now = datetime(2026, 2, 13, 12, 0, tzinfo=timezone.utc)
    state_since = datetime(2026, 2, 13, 11, 0, tzinfo=timezone.utc)

    since, source = resolve_ingest_since(
        symbol="BTC/USDT",
        timeframe="1m",
        state_since=state_since,
        last_time=None,
        disk_level="block",
        now=now,
    )

    assert since is None
    assert source == "blocked_storage_guard"


def test_resolve_ingest_since_rebootstraps_when_underfilled_even_with_db_last():
    now = datetime(2026, 2, 13, 12, 0, tzinfo=timezone.utc)
    state_since = datetime(2026, 2, 13, 11, 0, tzinfo=timezone.utc)
    db_last = datetime(2026, 2, 13, 10, 0, tzinfo=timezone.utc)

    since, source = resolve_ingest_since(
        symbol="BTC/USDT",
        timeframe="1h",
        state_since=state_since,
        last_time=db_last,
        disk_level="normal",
        force_rebootstrap=True,
        now=now,
    )

    assert source == "underfilled_rebootstrap"
    assert since == datetime(2026, 1, 14, 12, 0, tzinfo=timezone.utc)


def test_resolve_ingest_since_uses_exchange_earliest_for_1h_bootstrap():
    now = datetime(2026, 2, 13, 12, 0, tzinfo=timezone.utc)
    earliest = datetime(2020, 1, 1, 0, 0, tzinfo=timezone.utc)

    since, source = resolve_ingest_since(
        symbol="BTC/USDT",
        timeframe="1h",
        state_since=None,
        last_time=None,
        disk_level="normal",
        bootstrap_since=earliest,
        now=now,
    )

    assert source == "bootstrap_exchange_earliest"
    assert since == earliest


def test_resolve_ingest_since_uses_exchange_earliest_for_1h_state_drift():
    now = datetime(2026, 2, 13, 12, 0, tzinfo=timezone.utc)
    earliest = datetime(2020, 1, 1, 0, 0, tzinfo=timezone.utc)
    state_since = datetime(2026, 2, 13, 11, 0, tzinfo=timezone.utc)

    since, source = resolve_ingest_since(
        symbol="BTC/USDT",
        timeframe="1h",
        state_since=state_since,
        last_time=None,
        disk_level="normal",
        bootstrap_since=earliest,
        now=now,
    )

    assert source == "state_drift_rebootstrap_exchange_earliest"
    assert since == earliest


def test_resolve_ingest_since_enforces_full_backfill_for_hidden_1h():
    now = datetime(2026, 2, 13, 12, 0, tzinfo=timezone.utc)
    earliest = datetime(2020, 1, 1, 0, 0, tzinfo=timezone.utc)
    db_last = datetime(2026, 2, 13, 11, 0, tzinfo=timezone.utc)

    since, source = resolve_ingest_since(
        symbol="BTC/USDT",
        timeframe="1h",
        state_since=db_last,
        last_time=db_last,
        disk_level="normal",
        bootstrap_since=earliest,
        enforce_full_backfill=True,
        now=now,
    )

    assert source == "full_backfill_exchange_earliest"
    assert since == earliest


def test_get_last_timestamp_legacy_fallback_filters_missing_timeframe(
    monkeypatch,
):
    captured_queries = []
    expected = datetime(2026, 2, 13, 11, 0, tzinfo=timezone.utc)

    def fake_query_last_timestamp(query_api, query: str):
        captured_queries.append(query)
        if len(captured_queries) == 1:
            return None
        return expected

    monkeypatch.setattr("scripts.pipeline_worker.PRIMARY_TIMEFRAME", "1h")
    monkeypatch.setattr(
        "scripts.pipeline_worker._query_last_timestamp",
        fake_query_last_timestamp,
    )

    result = get_last_timestamp(
        query_api=object(),
        symbol="BTC/USDT",
        timeframe="1h",
    )

    assert result == expected
    assert len(captured_queries) == 2
    assert 'not exists r["timeframe"]' in captured_queries[1]


def test_get_first_timestamp_legacy_fallback_filters_missing_timeframe(
    monkeypatch,
):
    captured_queries = []
    expected = datetime(2020, 1, 1, 0, 0, tzinfo=timezone.utc)

    def fake_query_first_timestamp(query_api, query: str):
        captured_queries.append(query)
        if len(captured_queries) == 1:
            return None
        return expected

    monkeypatch.setattr("scripts.pipeline_worker.PRIMARY_TIMEFRAME", "1h")
    monkeypatch.setattr(
        "scripts.pipeline_worker._query_first_timestamp",
        fake_query_first_timestamp,
    )

    result = get_first_timestamp(
        query_api=object(),
        symbol="BTC/USDT",
        timeframe="1h",
    )

    assert result == expected
    assert len(captured_queries) == 2
    assert 'not exists r["timeframe"]' in captured_queries[1]


def test_build_runtime_manifest_marks_hidden_symbol_unservable(tmp_path):
    symbol = "BTC/USDT"
    timeframe = "1h"
    safe_symbol = symbol.replace("/", "_")
    now = datetime(2026, 2, 13, 12, 0, tzinfo=timezone.utc)

    history_path = tmp_path / f"history_{safe_symbol}_{timeframe}.json"
    history_path.write_text(
        json.dumps(
            {
                "symbol": symbol,
                "timeframe": timeframe,
                "updated_at": "2026-02-13T11:55:00Z",
                "data": [],
            }
        )
    )
    prediction_path = tmp_path / f"prediction_{safe_symbol}_{timeframe}.json"
    prediction_path.write_text(
        json.dumps(
            {
                "symbol": symbol,
                "timeframe": timeframe,
                "updated_at": "2026-02-13T11:56:00Z",
                "forecast": [],
            }
        )
    )

    manifest = build_runtime_manifest(
        [symbol],
        [timeframe],
        now=now,
        static_dir=tmp_path,
        prediction_health_path=tmp_path / "prediction_health.json",
        symbol_activation_entries={
            symbol: {
                "state": "backfilling",
                "visibility": "hidden_backfilling",
                "is_full_backfilled": False,
                "coverage_start_at": "2026-01-01T00:00:00Z",
                "coverage_end_at": "2026-02-13T11:00:00Z",
            }
        },
    )

    assert manifest["summary"]["visible_symbol_count"] == 0
    assert manifest["summary"]["hidden_symbol_count"] == 1
    entry = manifest["entries"][0]
    assert entry["visibility"] == "hidden_backfilling"
    assert entry["symbol_state"] == "backfilling"
    assert entry["serve_allowed"] is False


def test_minimum_required_lookback_rows_for_1h_only():
    assert _minimum_required_lookback_rows("1h", 30) == 576
    assert _minimum_required_lookback_rows("1d", 30) is None


def test_enforce_1m_retention_calls_delete_api(monkeypatch):
    fake_delete_api = FakeDeleteAPI()
    now = datetime(2026, 2, 13, 12, 0, tzinfo=timezone.utc)
    monkeypatch.setattr(
        "scripts.pipeline_worker.INFLUXDB_BUCKET", "market_data"
    )
    monkeypatch.setattr("scripts.pipeline_worker.INFLUXDB_ORG", "coin")

    enforce_1m_retention(
        fake_delete_api,
        ["BTC/USDT", "ETH/USDT"],
        now=now,
        retention_days=40,  # clamp to 30
    )

    assert len(fake_delete_api.calls) == 2
    first_call = fake_delete_api.calls[0]
    assert first_call["bucket"] == "market_data"
    assert first_call["org"] == "coin"
    assert first_call["predicate"].endswith('timeframe="1m"')
    assert first_call["stop"] == datetime(
        2026, 1, 14, 12, 0, tzinfo=timezone.utc
    )


def test_downsample_ohlcv_frame_filters_incomplete_bucket():
    base = datetime(2026, 2, 10, 0, 0, tzinfo=timezone.utc)
    rows = []
    for hour in range(24 + 12):
        ts = base + timedelta(hours=hour)
        rows.append(
            {
                "timestamp": ts,
                "open": float(hour + 1),
                "high": float(hour + 2),
                "low": float(hour),
                "close": float(hour + 1.5),
                "volume": 10.0,
            }
        )
    source_df = pd.DataFrame(rows).set_index("timestamp")

    complete_df, incomplete_df = downsample_ohlcv_frame(
        source_df, target_timeframe="1d"
    )

    assert len(complete_df) == 1
    assert len(incomplete_df) == 1
    first_bucket = complete_df.iloc[0]
    assert first_bucket["open"] == 1.0
    assert first_bucket["close"] == 24.5
    assert first_bucket["high"] == 25.0
    assert first_bucket["low"] == 0.0
    assert first_bucket["volume"] == 240.0
    assert incomplete_df.iloc[0]["source_count"] == 12
    assert incomplete_df.iloc[0]["expected_count"] == 24


def test_run_downsample_and_save_writes_ohlcv_and_lineage(
    tmp_path, monkeypatch
):
    base = datetime(2026, 2, 10, 0, 0, tzinfo=timezone.utc)
    rows = []
    for hour in range(48):
        ts = base + timedelta(hours=hour)
        rows.append(
            {
                "_time": ts,
                "open": float(hour + 1),
                "high": float(hour + 2),
                "low": float(hour),
                "close": float(hour + 1.5),
                "volume": 10.0,
            }
        )
    query_df = pd.DataFrame(rows)
    query_api = FakeQueryAPI(query_df)
    write_api = FakeWriteAPI()

    lineage_path = tmp_path / "downsample_lineage.json"
    monkeypatch.setattr(
        "scripts.pipeline_worker.DOWNSAMPLE_LINEAGE_FILE", lineage_path
    )
    monkeypatch.setattr(
        "scripts.pipeline_worker.INFLUXDB_BUCKET", "market_data"
    )
    monkeypatch.setattr("scripts.pipeline_worker.INFLUXDB_ORG", "coin")

    latest_saved_at, result = run_downsample_and_save(
        write_api,
        query_api,
        symbol="BTC/USDT",
        target_timeframe="1d",
    )

    assert result == "saved"
    assert latest_saved_at == datetime(2026, 2, 11, 0, 0, tzinfo=timezone.utc)
    assert len(write_api.calls) == 1
    write_call = write_api.calls[0]
    assert write_call["bucket"] == "market_data"
    assert write_call["org"] == "coin"
    saved_df = write_call["record"]
    assert len(saved_df) == 2
    assert list(saved_df["timeframe"].unique()) == ["1d"]
    assert list(saved_df["symbol"].unique()) == ["BTC/USDT"]

    lineage_payload = json.loads(lineage_path.read_text())
    entry = lineage_payload["entries"]["BTC/USDT|1d"]
    assert entry["source_timeframe"] == "1h"
    assert entry["source_rows"] == 48
    assert entry["complete_buckets"] == 2
    assert entry["incomplete_buckets"] == 0
    assert entry["status"] == "ok"
