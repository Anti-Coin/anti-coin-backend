import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace

import pandas as pd

from scripts.pipeline_worker import (
    _detect_gaps_from_ms_timestamps,
    _evaluate_underfill_rebootstrap,
    _fetch_ohlcv_paginated,
    _lookback_days_for_timeframe,
    _minimum_required_lookback_rows,
    _record_ingest_outcome_state,
    _refill_detected_gaps,
    _run_ingest_timeframe_step,
    _run_publish_timeframe_step,
    WorkerPersistentState,
    append_runtime_cycle_metrics,
    build_runtime_manifest,
    evaluate_detection_gate,
    enforce_1m_retention,
    get_first_timestamp,
    get_disk_usage_percent,
    get_exchange_latest_closed_timestamp,
    get_last_timestamp,
    initialize_boundary_schedule,
    prediction_enabled_for_timeframe,
    resolve_boundary_due_timeframes,
    resolve_ingest_since,
    resolve_disk_watermark_level,
    run_ingest_step,
    run_prediction_and_save,
    save_history_to_json,
    should_block_initial_backfill,
    should_enforce_1m_retention,
    update_full_history_file,
    upsert_prediction_health,
    write_runtime_manifest,
)
from utils.ingest_state import IngestStateStore
from utils.pipeline_contracts import (
    IngestExecutionOutcome,
    IngestExecutionResult,
    PredictionExecutionResult,
    StorageGuardLevel,
    SymbolActivationSnapshot,
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
        self,
        symbol: str,
        timeframe: str,
        since: int | None = None,
        limit: int | None = None,
    ) -> list[list[float]]:
        if since is None:
            candidates = self._candles
        else:
            candidates = [row for row in self._candles if row[0] >= since]
        if limit is None:
            return candidates
        return candidates[:limit]


class FakeDeleteAPI:
    def __init__(self):
        self.calls = []

    def delete(self, **kwargs):
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
        query_api=None,
        symbol="BTC/USDT",
        timeframe="1m",
    )
    assert result == "skipped"
    assert error is None


def test_min_sample_gate_blocks_insufficient_data(monkeypatch):
    """D-010: 샘플 미달 시 'skipped' + 'insufficient_data' 반환"""
    monkeypatch.setattr(
        "scripts.pipeline_worker.PREDICTION_DISABLED_TIMEFRAMES",
        {"1m"},
    )
    monkeypatch.setattr(
        "scripts.pipeline_worker.MIN_SAMPLE_BY_TIMEFRAME",
        {"1d": 120},
    )
    # count_ohlcv_rows가 미달 값을 반환하도록 monkeypatch
    monkeypatch.setattr(
        "scripts.pipeline_worker.count_ohlcv_rows",
        lambda query_api, *, symbol, timeframe: 50,
    )
    result, error = run_prediction_and_save(
        write_api=None,
        query_api=None,
        symbol="BTC/USDT",
        timeframe="1d",
    )
    assert result == "skipped"
    assert error == "insufficient_data"


def test_min_sample_gate_allows_sufficient_data(monkeypatch):
    """D-010: 샘플 충분 시 gate 통과 (모델 없으므로 'failed' + 'model_missing')"""
    monkeypatch.setattr(
        "scripts.pipeline_worker.PREDICTION_DISABLED_TIMEFRAMES",
        {"1m"},
    )
    monkeypatch.setattr(
        "scripts.pipeline_worker.MIN_SAMPLE_BY_TIMEFRAME",
        {"1d": 120},
    )
    monkeypatch.setattr(
        "scripts.pipeline_worker.count_ohlcv_rows",
        lambda query_api, *, symbol, timeframe: 500,
    )
    monkeypatch.setattr(
        "scripts.pipeline_worker.MODELS_DIR",
        Path("/nonexistent_models_dir"),
    )
    result, error = run_prediction_and_save(
        write_api=None,
        query_api=None,
        symbol="BTC/USDT",
        timeframe="1d",
    )
    # 모델 파일이 없으므로 gate를 통과하고 model_missing에서 실패해야 한다.
    assert result == "failed"
    assert error == "model_missing"


def test_min_sample_gate_skips_unknown_timeframe(monkeypatch):
    """D-010: MIN_SAMPLE_BY_TIMEFRAME에 없는 TF는 gate 없이 통과"""
    monkeypatch.setattr(
        "scripts.pipeline_worker.PREDICTION_DISABLED_TIMEFRAMES",
        {"1m"},
    )
    monkeypatch.setattr(
        "scripts.pipeline_worker.MIN_SAMPLE_BY_TIMEFRAME",
        {"1d": 120},  # 4h는 없음
    )
    monkeypatch.setattr(
        "scripts.pipeline_worker.MODELS_DIR",
        Path("/nonexistent_models_dir"),
    )
    result, error = run_prediction_and_save(
        write_api=None,
        query_api=None,
        symbol="BTC/USDT",
        timeframe="4h",
    )
    # gate 적용 안 됨, 모델 없어서 model_missing
    assert result == "failed"
    assert error == "model_missing"


def test_save_history_to_json_writes_timeframe_aware_files(tmp_path, monkeypatch):
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
        ingest_since_source_counts={"db_last": 5, "bootstrap_lookback": 1},
        detection_gate_run_counts={"new_closed_candle": 2},
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
        ingest_since_source_counts={
            "underfilled_rebootstrap": 2,
            "blocked_storage_guard": 1,
        },
        detection_gate_skip_counts={"no_new_closed_candle": 3},
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
    assert payload["summary"]["ingest_since_source_counts"]["db_last"] == 5
    assert (
        payload["summary"]["ingest_since_source_counts"]["underfilled_rebootstrap"] == 2
    )
    assert payload["summary"]["rebootstrap_cycles"] == 1
    assert payload["summary"]["rebootstrap_events"] == 2
    assert payload["summary"]["underfill_guard_retrigger_cycles"] == 1
    assert payload["summary"]["underfill_guard_retrigger_events"] == 2
    assert payload["summary"]["detection_gate_run_counts"]["new_closed_candle"] == 2
    assert payload["summary"]["detection_gate_run_events"] == 2
    assert payload["summary"]["detection_gate_skip_counts"]["no_new_closed_candle"] == 3
    assert payload["summary"]["detection_gate_skip_events"] == 3
    assert payload["recent_cycles"][1]["ingest_since_source_counts"] == {
        "underfilled_rebootstrap": 2,
        "blocked_storage_guard": 1,
    }
    assert payload["recent_cycles"][0]["detection_gate_run_counts"] == {
        "new_closed_candle": 2
    }
    assert payload["recent_cycles"][1]["detection_gate_skip_counts"] == {
        "no_new_closed_candle": 3
    }
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


def test_append_runtime_cycle_metrics_ignores_invalid_source_counts(tmp_path):
    metrics_path = tmp_path / "runtime_metrics.json"
    base = datetime(2026, 2, 13, 12, 0, tzinfo=timezone.utc)

    append_runtime_cycle_metrics(
        started_at=base,
        elapsed_seconds=9.0,
        sleep_seconds=51.0,
        overrun=False,
        cycle_result="ok",
        ingest_since_source_counts={
            "db_last": "not_a_number",
            "": 3,
            "underfilled_rebootstrap": -1,
            "bootstrap_lookback": 2,
        },
        path=metrics_path,
    )

    payload = json.loads(metrics_path.read_text())
    assert payload["recent_cycles"][0]["ingest_since_source_counts"] == {
        "bootstrap_lookback": 2
    }
    assert payload["summary"]["ingest_since_source_counts"] == {"bootstrap_lookback": 2}
    assert payload["summary"]["rebootstrap_events"] == 0


def test_append_runtime_cycle_metrics_boundary_mode_tracks_missed_boundary(
    tmp_path,
):
    metrics_path = tmp_path / "runtime_metrics.json"
    base = datetime(2026, 2, 13, 12, 0, tzinfo=timezone.utc)

    append_runtime_cycle_metrics(
        started_at=base,
        elapsed_seconds=61.0,
        sleep_seconds=0.0,
        overrun=True,
        cycle_result="ok",
        boundary_tracking_mode="boundary_scheduler",
        missed_boundary_count=2,
        path=metrics_path,
    )

    payload = json.loads(metrics_path.read_text())
    assert payload["boundary_tracking"]["mode"] == "boundary_scheduler"
    assert payload["boundary_tracking"]["missed_boundary_supported"] is True
    assert payload["summary"]["missed_boundary_count"] == 2
    assert payload["summary"]["missed_boundary_rate"] == 2.0
    assert payload["recent_cycles"][0]["scheduler_mode"] == "boundary_scheduler"
    assert payload["recent_cycles"][0]["missed_boundary_count"] == 2


def test_append_runtime_cycle_metrics_boundary_mode_zero_missed(tmp_path):
    metrics_path = tmp_path / "runtime_metrics.json"
    base = datetime(2026, 2, 13, 12, 0, tzinfo=timezone.utc)

    append_runtime_cycle_metrics(
        started_at=base,
        elapsed_seconds=20.0,
        sleep_seconds=40.0,
        overrun=False,
        cycle_result="ok",
        boundary_tracking_mode="boundary_scheduler",
        missed_boundary_count=0,
        path=metrics_path,
    )

    payload = json.loads(metrics_path.read_text())
    assert payload["summary"]["missed_boundary_count"] == 0
    assert payload["summary"]["missed_boundary_rate"] == 0.0


def test_resolve_boundary_due_timeframes_counts_missed_boundaries():
    now = datetime(2026, 2, 13, 10, 0, tzinfo=timezone.utc)
    schedule = {
        "1h": datetime(2026, 2, 13, 9, 0, tzinfo=timezone.utc),
        "1d": datetime(2026, 2, 14, 0, 0, tzinfo=timezone.utc),
    }

    due, missed, next_boundary_at = resolve_boundary_due_timeframes(
        now=now,
        timeframes=["1h", "1d"],
        next_boundary_by_timeframe=schedule,
    )

    assert due == ["1h"]
    assert missed == 1
    assert schedule["1h"] == datetime(2026, 2, 13, 11, 0, tzinfo=timezone.utc)
    assert next_boundary_at == datetime(2026, 2, 13, 11, 0, tzinfo=timezone.utc)


def test_resolve_boundary_due_timeframes_without_missed_boundary():
    now = datetime(2026, 2, 13, 10, 0, tzinfo=timezone.utc)
    schedule = {"1h": datetime(2026, 2, 13, 10, 0, tzinfo=timezone.utc)}

    due, missed, next_boundary_at = resolve_boundary_due_timeframes(
        now=now,
        timeframes=["1h"],
        next_boundary_by_timeframe=schedule,
    )

    assert due == ["1h"]
    assert missed == 0
    assert next_boundary_at == datetime(2026, 2, 13, 11, 0, tzinfo=timezone.utc)


def test_initialize_boundary_schedule_sets_next_boundaries():
    now = datetime(2026, 2, 13, 10, 37, tzinfo=timezone.utc)
    schedule = initialize_boundary_schedule(now, ["1h", "1d"])
    assert schedule["1h"] == datetime(2026, 2, 13, 10, 0, tzinfo=timezone.utc)
    assert schedule["1d"] == datetime(2026, 2, 13, 0, 0, tzinfo=timezone.utc)


def test_initialize_boundary_schedule_catches_up_long_timeframes_on_start():
    now = datetime(2026, 2, 19, 8, 2, tzinfo=timezone.utc)
    schedule = initialize_boundary_schedule(now, ["1h", "1d", "1w", "1M"])

    due, missed, next_boundary_at = resolve_boundary_due_timeframes(
        now=now,
        timeframes=["1h", "1d", "1w", "1M"],
        next_boundary_by_timeframe=schedule,
    )

    assert due == ["1h", "1d", "1w", "1M"]
    assert missed == 0
    assert next_boundary_at == datetime(2026, 2, 19, 9, 0, tzinfo=timezone.utc)


def test_get_exchange_latest_closed_timestamp_ignores_open_candle():
    now = datetime(2026, 2, 13, 10, 37, tzinfo=timezone.utc)
    base = datetime(2026, 2, 13, 8, 0, tzinfo=timezone.utc)
    candles = [
        [_to_ms(base), 1.0, 1.0, 1.0, 1.0, 1.0],
        [_to_ms(base + timedelta(hours=1)), 1.0, 1.0, 1.0, 1.0, 1.0],
        [_to_ms(base + timedelta(hours=2)), 1.0, 1.0, 1.0, 1.0, 1.0],
    ]
    exchange = FakeExchange(candles)

    latest = get_exchange_latest_closed_timestamp(
        exchange,
        "BTC/USDT",
        "1h",
        now=now,
    )

    assert latest == datetime(2026, 2, 13, 9, 0, tzinfo=timezone.utc)


def test_evaluate_detection_gate_skips_when_no_new_closed_candle():
    now = datetime(2026, 2, 13, 10, 37, tzinfo=timezone.utc)
    last_saved = datetime(2026, 2, 13, 9, 0, tzinfo=timezone.utc)
    candles = [
        [
            _to_ms(datetime(2026, 2, 13, 9, 0, tzinfo=timezone.utc)),
            1,
            1,
            1,
            1,
            1,
        ],
        [
            _to_ms(datetime(2026, 2, 13, 10, 0, tzinfo=timezone.utc)),
            1,
            1,
            1,
            1,
            1,
        ],
    ]
    exchange = FakeExchange(candles)

    should_run, reason = evaluate_detection_gate(
        query_api=object(),
        detection_exchange=exchange,
        symbol="BTC/USDT",
        timeframe="1h",
        now=now,
        last_saved=last_saved,
    )

    assert should_run is False
    assert reason == "no_new_closed_candle"


def test_evaluate_detection_gate_runs_when_detection_unavailable(monkeypatch):
    monkeypatch.setattr(
        "scripts.pipeline_worker.get_exchange_latest_closed_timestamp",
        lambda *args, **kwargs: None,
    )

    should_run, reason = evaluate_detection_gate(
        query_api=object(),
        detection_exchange=object(),
        symbol="BTC/USDT",
        timeframe="1h",
        now=datetime(2026, 2, 13, 10, 37, tzinfo=timezone.utc),
        last_saved=None,
    )

    assert should_run is True
    assert reason == "detection_unavailable_fallback_run"


def test_evaluate_detection_gate_1d_skips_when_no_new_closed_candle():
    now = datetime(2026, 2, 14, 0, 10, tzinfo=timezone.utc)
    last_saved = datetime(2026, 2, 13, 0, 0, tzinfo=timezone.utc)
    candles = [
        [_to_ms(datetime(2026, 2, 12, 0, 0, tzinfo=timezone.utc)), 1, 1, 1, 1, 1],
        [_to_ms(datetime(2026, 2, 13, 0, 0, tzinfo=timezone.utc)), 1, 1, 1, 1, 1],
    ]
    exchange = SimpleNamespace(fetch_ohlcv=lambda *args, **kwargs: candles)

    should_run, reason = evaluate_detection_gate(
        query_api=object(),
        detection_exchange=exchange,
        symbol="BTC/USDT",
        timeframe="1d",
        now=now,
        last_saved=last_saved,
    )

    assert should_run is False
    assert reason == "no_new_closed_candle"


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
    assert should_enforce_1m_retention(now - timedelta(minutes=59), now) is False
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


def test_resolve_ingest_since_uses_exchange_earliest_for_1d_bootstrap():
    now = datetime(2026, 2, 13, 12, 0, tzinfo=timezone.utc)
    earliest = datetime(2020, 1, 1, 0, 0, tzinfo=timezone.utc)

    since, source = resolve_ingest_since(
        symbol="BTC/USDT",
        timeframe="1d",
        state_since=None,
        last_time=None,
        disk_level="normal",
        bootstrap_since=earliest,
        now=now,
    )

    assert source == "bootstrap_exchange_earliest"
    assert since == earliest


def test_resolve_ingest_since_uses_exchange_earliest_for_1w_state_drift():
    now = datetime(2026, 2, 13, 12, 0, tzinfo=timezone.utc)
    earliest = datetime(2020, 1, 6, 0, 0, tzinfo=timezone.utc)
    state_since = datetime(2026, 2, 13, 11, 0, tzinfo=timezone.utc)

    since, source = resolve_ingest_since(
        symbol="BTC/USDT",
        timeframe="1w",
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


def test_resolve_ingest_since_force_rebootstrap_uses_exchange_earliest_for_fullfill_tf():
    """D-020: full-fill TF의 force_rebootstrap은 exchange earliest부터 재수집한다."""
    now = datetime(2026, 2, 13, 12, 0, tzinfo=timezone.utc)
    earliest = datetime(2020, 1, 1, 0, 0, tzinfo=timezone.utc)
    db_last = datetime(2026, 2, 13, 10, 0, tzinfo=timezone.utc)

    since, source = resolve_ingest_since(
        symbol="BTC/USDT",
        timeframe="1d",
        state_since=db_last,
        last_time=db_last,
        disk_level="normal",
        force_rebootstrap=True,
        bootstrap_since=earliest,
        now=now,
    )

    assert source == "underfilled_rebootstrap_exchange_earliest"
    assert since == earliest


def test_resolve_ingest_since_force_rebootstrap_uses_lookback_for_non_fullfill_tf():
    """D-020: 비full-fill TF의 force_rebootstrap은 기존 lookback 방식을 유지한다."""
    now = datetime(2026, 2, 13, 12, 0, tzinfo=timezone.utc)

    since, source = resolve_ingest_since(
        symbol="BTC/USDT",
        timeframe="1m",
        state_since=None,
        last_time=None,
        disk_level="normal",
        force_rebootstrap=True,
        bootstrap_since=datetime(2020, 1, 1, 0, 0, tzinfo=timezone.utc),
        now=now,
    )

    assert source == "underfilled_rebootstrap"
    assert since == datetime(2026, 1, 30, 12, 0, tzinfo=timezone.utc)


def test_evaluate_underfill_rebootstrap_detects_backward_gap(monkeypatch):
    """D-020: DB first가 exchange earliest보다 한참 늦으면 rebootstrap을 트리거한다."""
    exchange_earliest = datetime(2020, 1, 1, 0, 0, tzinfo=timezone.utc)
    db_first = datetime(2026, 1, 23, 0, 0, tzinfo=timezone.utc)

    monkeypatch.setattr(
        "scripts.pipeline_worker._minimum_required_lookback_rows",
        lambda *args, **kwargs: None,
    )
    monkeypatch.setattr(
        "scripts.pipeline_worker.get_first_timestamp",
        lambda *args, **kwargs: db_first,
    )

    _, force_rebootstrap = _evaluate_underfill_rebootstrap(
        query_api=object(),
        symbol="BTC/USDT",
        timeframe="1d",
        exchange_earliest=exchange_earliest,
    )

    assert force_rebootstrap is True


def test_evaluate_underfill_rebootstrap_skips_when_filled(monkeypatch):
    """D-020: DB first가 exchange earliest와 가까우면 rebootstrap하지 않는다."""
    exchange_earliest = datetime(2020, 1, 1, 0, 0, tzinfo=timezone.utc)
    db_first = datetime(2020, 1, 1, 0, 0, tzinfo=timezone.utc)

    monkeypatch.setattr(
        "scripts.pipeline_worker._minimum_required_lookback_rows",
        lambda *args, **kwargs: None,
    )
    monkeypatch.setattr(
        "scripts.pipeline_worker.get_first_timestamp",
        lambda *args, **kwargs: db_first,
    )

    _, force_rebootstrap = _evaluate_underfill_rebootstrap(
        query_api=object(),
        symbol="BTC/USDT",
        timeframe="1d",
        exchange_earliest=exchange_earliest,
    )

    assert force_rebootstrap is False


def test_evaluate_underfill_rebootstrap_skips_backward_for_non_fullfill_tf(monkeypatch):
    """D-020: 비full-fill TF (1m)에서는 backward check를 수행하지 않는다."""
    monkeypatch.setattr(
        "scripts.pipeline_worker._minimum_required_lookback_rows",
        lambda *args, **kwargs: None,
    )

    _, force_rebootstrap = _evaluate_underfill_rebootstrap(
        query_api=object(),
        symbol="BTC/USDT",
        timeframe="1m",
        exchange_earliest=datetime(2020, 1, 1, 0, 0, tzinfo=timezone.utc),
    )

    assert force_rebootstrap is False


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
    monkeypatch.setattr("scripts.worker_guards.INFLUXDB_BUCKET", "market_data")
    monkeypatch.setattr("scripts.worker_guards.INFLUXDB_ORG", "coin")

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
    assert first_call["stop"] == datetime(2026, 1, 14, 12, 0, tzinfo=timezone.utc)


def test_record_ingest_outcome_state_saved_commits_cursor_and_watermark(
    tmp_path,
):
    symbol = "BTC/USDT"
    timeframe = "1h"
    latest_saved_at = datetime(2026, 2, 18, 12, 0, tzinfo=timezone.utc)
    key = f"{symbol}|{timeframe}"
    state = WorkerPersistentState(
        symbol_activation_entries={},
        ingest_watermarks={},
    )
    ingest_state_store = IngestStateStore(tmp_path / "ingest_state.json")

    _record_ingest_outcome_state(
        ingest_state_store=ingest_state_store,
        state=state,
        symbol=symbol,
        timeframe=timeframe,
        previous_last_closed_ts=None,
        ingest_outcome=IngestExecutionOutcome(
            latest_saved_at=latest_saved_at,
            result=IngestExecutionResult.SAVED,
        ),
    )

    entry = ingest_state_store.get(symbol, timeframe)
    assert entry is not None
    assert entry.status == "ok"
    assert entry.last_closed_ts == latest_saved_at
    assert state.ingest_watermarks[key].closed_at == latest_saved_at


def test_record_ingest_outcome_state_failure_keeps_watermark_and_marks_failed(
    tmp_path,
):
    symbol = "BTC/USDT"
    timeframe = "1h"
    key = f"{symbol}|{timeframe}"
    previous_last_closed_ts = datetime(2026, 2, 18, 11, 0, tzinfo=timezone.utc)
    previous_watermark = datetime(2026, 2, 18, 10, 0, tzinfo=timezone.utc)
    state = WorkerPersistentState(
        symbol_activation_entries={},
        ingest_watermarks={key: previous_watermark.strftime("%Y-%m-%dT%H:%M:%SZ")},
    )
    ingest_state_store = IngestStateStore(tmp_path / "ingest_state.json")

    for failure_result in (
        IngestExecutionResult.FAILED,
        IngestExecutionResult.UNSUPPORTED,
    ):
        _record_ingest_outcome_state(
            ingest_state_store=ingest_state_store,
            state=state,
            symbol=symbol,
            timeframe=timeframe,
            previous_last_closed_ts=previous_last_closed_ts,
            ingest_outcome=IngestExecutionOutcome(
                latest_saved_at=None,
                result=failure_result,
            ),
        )
        entry = ingest_state_store.get(symbol, timeframe)
        assert entry is not None
        assert entry.status == "failed"
        assert entry.last_closed_ts == previous_last_closed_ts
        assert state.ingest_watermarks[key] == "2026-02-18T10:00:00Z"


def test_run_ingest_timeframe_step_blocked_storage_guard_stops_without_watermark(
    monkeypatch, tmp_path
):
    symbol = "BTC/USDT"
    timeframe = "1m"
    now = datetime(2026, 2, 19, 12, 0, tzinfo=timezone.utc)
    key = f"{symbol}|{timeframe}"
    state = WorkerPersistentState(
        symbol_activation_entries={},
        ingest_watermarks={},
    )
    ingest_state_store = IngestStateStore(tmp_path / "ingest_state.json")
    activation = SymbolActivationSnapshot.from_payload(
        symbol=symbol,
        payload={
            "symbol": symbol,
            "state": "ready_for_serving",
            "visibility": "visible",
            "is_full_backfilled": True,
            "updated_at": "2026-02-19T11:00:00Z",
        },
        fallback_now=now,
    )

    monkeypatch.setattr(
        "scripts.pipeline_worker.resolve_ingest_since",
        lambda **kwargs: (None, "blocked_storage_guard"),
    )
    monkeypatch.setattr(
        "scripts.pipeline_worker.get_last_timestamp",
        lambda *args, **kwargs: None,
    )

    should_continue_publish, next_activation = _run_ingest_timeframe_step(
        write_api=object(),
        query_api=object(),
        activation_exchange=object(),
        ingest_state_store=ingest_state_store,
        symbol=symbol,
        timeframe=timeframe,
        cycle_now=now,
        scheduler_mode="poll_loop",
        symbol_activation=activation,
        exchange_earliest=None,
        disk_level=StorageGuardLevel.BLOCK,
        disk_usage_percent=92.5,
        state=state,
        cycle_since_source_counts={},
        cycle_detection_skip_counts={},
        cycle_detection_run_counts={},
    )

    assert should_continue_publish is False
    assert next_activation == activation
    entry = ingest_state_store.get(symbol, timeframe)
    assert entry is not None
    assert entry.status == "blocked_storage_guard"
    assert key not in state.ingest_watermarks


def test_run_ingest_timeframe_step_reads_db_last_with_full_range_for_1d(
    monkeypatch, tmp_path
):
    symbol = "BTC/USDT"
    timeframe = "1d"
    now = datetime(2026, 2, 19, 12, 0, tzinfo=timezone.utc)
    state = WorkerPersistentState(
        symbol_activation_entries={},
        ingest_watermarks={},
    )
    ingest_state_store = IngestStateStore(tmp_path / "ingest_state.json")
    activation = SymbolActivationSnapshot.from_payload(
        symbol=symbol,
        payload={
            "symbol": symbol,
            "state": "ready_for_serving",
            "visibility": "visible",
            "is_full_backfilled": True,
            "updated_at": "2026-02-19T11:00:00Z",
        },
        fallback_now=now,
    )

    last_timestamp_calls: list[bool] = []

    def fake_get_last_timestamp(*args, **kwargs):
        last_timestamp_calls.append(bool(kwargs.get("full_range", False)))
        return None

    monkeypatch.setattr(
        "scripts.pipeline_worker.get_last_timestamp",
        fake_get_last_timestamp,
    )
    monkeypatch.setattr(
        "scripts.pipeline_worker.resolve_ingest_since",
        lambda **kwargs: (None, "blocked_storage_guard"),
    )

    should_continue_publish, next_activation = _run_ingest_timeframe_step(
        write_api=object(),
        query_api=object(),
        activation_exchange=object(),
        ingest_state_store=ingest_state_store,
        symbol=symbol,
        timeframe=timeframe,
        cycle_now=now,
        scheduler_mode="poll_loop",
        symbol_activation=activation,
        exchange_earliest=datetime(2020, 1, 1, tzinfo=timezone.utc),
        disk_level=StorageGuardLevel.BLOCK,
        disk_usage_percent=92.5,
        state=state,
        cycle_since_source_counts={},
        cycle_detection_skip_counts={},
        cycle_detection_run_counts={},
    )

    assert should_continue_publish is False
    assert next_activation == activation
    assert last_timestamp_calls == [True]


def test_run_ingest_timeframe_step_long_tf_skip_syncs_watermark_and_allows_publish(
    monkeypatch, tmp_path
):
    symbol = "BTC/USDT"
    timeframe = "1d"
    now = datetime(2026, 2, 19, 12, 0, tzinfo=timezone.utc)
    latest_saved_at = datetime(2026, 2, 19, 0, 0, tzinfo=timezone.utc)
    key = f"{symbol}|{timeframe}"
    state = WorkerPersistentState(
        symbol_activation_entries={},
        ingest_watermarks={},
    )
    ingest_state_store = IngestStateStore(tmp_path / "ingest_state.json")
    activation = SymbolActivationSnapshot.from_payload(
        symbol=symbol,
        payload={
            "symbol": symbol,
            "state": "ready_for_serving",
            "visibility": "visible",
            "is_full_backfilled": True,
            "updated_at": "2026-02-19T11:00:00Z",
        },
        fallback_now=now,
    )

    monkeypatch.setattr(
        "scripts.pipeline_worker.get_last_timestamp",
        lambda *args, **kwargs: latest_saved_at,
    )
    monkeypatch.setattr(
        "scripts.pipeline_worker.evaluate_detection_gate_decision",
        lambda *args, **kwargs: SimpleNamespace(
            should_run=False,
            reason=SimpleNamespace(value="no_new_closed_candle"),
        ),
    )

    cycle_detection_skip_counts = {}
    should_continue_publish, next_activation = _run_ingest_timeframe_step(
        write_api=object(),
        query_api=object(),
        activation_exchange=object(),
        ingest_state_store=ingest_state_store,
        symbol=symbol,
        timeframe=timeframe,
        cycle_now=now,
        scheduler_mode="boundary",
        symbol_activation=activation,
        exchange_earliest=None,
        disk_level=StorageGuardLevel.NORMAL,
        disk_usage_percent=60.0,
        state=state,
        cycle_since_source_counts={},
        cycle_detection_skip_counts=cycle_detection_skip_counts,
        cycle_detection_run_counts={},
    )

    assert should_continue_publish is True
    assert next_activation == activation
    assert cycle_detection_skip_counts == {"no_new_closed_candle": 1}
    assert state.ingest_watermarks[key].closed_at == latest_saved_at


def test_run_ingest_timeframe_step_non_materialized_skip_still_blocks_publish(
    monkeypatch, tmp_path
):
    symbol = "BTC/USDT"
    timeframe = "1h"
    now = datetime(2026, 2, 19, 12, 0, tzinfo=timezone.utc)
    key = f"{symbol}|{timeframe}"
    previous_watermark = datetime(2026, 2, 19, 10, 0, tzinfo=timezone.utc)
    state = WorkerPersistentState(
        symbol_activation_entries={},
        ingest_watermarks={key: previous_watermark.strftime("%Y-%m-%dT%H:%M:%SZ")},
    )
    ingest_state_store = IngestStateStore(tmp_path / "ingest_state.json")
    activation = SymbolActivationSnapshot.from_payload(
        symbol=symbol,
        payload={
            "symbol": symbol,
            "state": "ready_for_serving",
            "visibility": "visible",
            "is_full_backfilled": True,
            "updated_at": "2026-02-19T11:00:00Z",
        },
        fallback_now=now,
    )

    monkeypatch.setattr(
        "scripts.pipeline_worker.get_last_timestamp",
        lambda *args, **kwargs: datetime(2026, 2, 19, 11, 0, tzinfo=timezone.utc),
    )
    monkeypatch.setattr(
        "scripts.pipeline_worker.evaluate_detection_gate_decision",
        lambda *args, **kwargs: SimpleNamespace(
            should_run=False,
            reason=SimpleNamespace(value="no_new_closed_candle"),
        ),
    )

    cycle_detection_skip_counts = {}
    should_continue_publish, next_activation = _run_ingest_timeframe_step(
        write_api=object(),
        query_api=object(),
        activation_exchange=object(),
        ingest_state_store=ingest_state_store,
        symbol=symbol,
        timeframe=timeframe,
        cycle_now=now,
        scheduler_mode="boundary",
        symbol_activation=activation,
        exchange_earliest=None,
        disk_level=StorageGuardLevel.NORMAL,
        disk_usage_percent=60.0,
        state=state,
        cycle_since_source_counts={},
        cycle_detection_skip_counts=cycle_detection_skip_counts,
        cycle_detection_run_counts={},
    )

    assert should_continue_publish is False
    assert next_activation == activation
    assert cycle_detection_skip_counts == {"no_new_closed_candle": 1}
    assert state.ingest_watermarks[key] == "2026-02-19T10:00:00Z"


def test_run_ingest_step_routes_long_timeframes_to_exchange_fetch(monkeypatch):
    expected_latest = datetime(2026, 2, 12, 0, 0, tzinfo=timezone.utc)
    expected_since = datetime(2026, 2, 1, 0, 0, tzinfo=timezone.utc)
    called_timeframes: list[str] = []

    def fake_fetch(write_api, symbol, since, timeframe):
        assert symbol == "BTC/USDT"
        assert since == expected_since
        called_timeframes.append(timeframe)
        return expected_latest, "saved"

    monkeypatch.setattr("scripts.pipeline_worker.fetch_and_save", fake_fetch)

    for timeframe in ("1d", "1w", "1M"):
        latest, result = run_ingest_step(
            write_api=object(),
            query_api=object(),
            symbol="BTC/USDT",
            timeframe=timeframe,
            since=expected_since,
        )
        assert latest == expected_latest
        assert result == "saved"

    assert called_timeframes == ["1d", "1w", "1M"]


def test_run_ingest_step_routes_base_to_exchange_fetch(monkeypatch):
    expected_latest = datetime(2026, 2, 12, 1, 0, tzinfo=timezone.utc)
    expected_since = datetime(2026, 2, 1, 0, 0, tzinfo=timezone.utc)

    def fake_fetch(write_api, symbol, since, timeframe):
        assert symbol == "BTC/USDT"
        assert since == expected_since
        assert timeframe == "1h"
        return expected_latest, "saved"

    monkeypatch.setattr("scripts.pipeline_worker.fetch_and_save", fake_fetch)

    latest, result = run_ingest_step(
        write_api=object(),
        query_api=object(),
        symbol="BTC/USDT",
        timeframe="1h",
        since=expected_since,
    )

    assert latest == expected_latest
    assert result == "saved"


def test_run_publish_timeframe_step_runs_export_with_ingest_watermark(
    monkeypatch,
):
    symbol = "BTC/USDT"
    timeframe = "1h"
    now = datetime(2026, 2, 24, 1, 0, tzinfo=timezone.utc)
    key = f"{symbol}|{timeframe}"
    watermark_text = "2026-02-24T01:00:00Z"

    state = WorkerPersistentState(
        symbol_activation_entries={},
        ingest_watermarks={key: watermark_text},
    )
    activation = SymbolActivationSnapshot.from_payload(
        symbol=symbol,
        payload={
            "symbol": symbol,
            "state": "ready_for_serving",
            "visibility": "visible",
            "is_full_backfilled": True,
            "updated_at": "2026-02-24T01:00:00Z",
        },
        fallback_now=now,
    )
    calls = {"export": 0}

    def fake_update_full_history_file(query_api, target_symbol, target_timeframe):
        assert target_symbol == symbol
        assert target_timeframe == timeframe
        calls["export"] += 1
        return True

    monkeypatch.setattr(
        "scripts.pipeline_worker.update_full_history_file",
        fake_update_full_history_file,
    )

    cycle_export_gate_skip_counts: dict[str, int] = {}
    _run_publish_timeframe_step(
        write_api=object(),
        query_api=object(),
        symbol=symbol,
        timeframe=timeframe,
        cycle_now=now,
        symbol_activation=activation,
        run_export_stage=True,
        run_predict_stage=False,
        state=state,
        cycle_export_gate_skip_counts=cycle_export_gate_skip_counts,
        cycle_predict_gate_skip_counts={},
    )

    assert calls["export"] == 1
    assert cycle_export_gate_skip_counts == {}


def test_run_publish_timeframe_step_runs_prediction_with_ingest_watermark(
    monkeypatch,
):
    symbol = "BTC/USDT"
    timeframe = "1h"
    now = datetime(2026, 2, 24, 1, 0, tzinfo=timezone.utc)
    key = f"{symbol}|{timeframe}"
    watermark_text = "2026-02-24T01:00:00Z"

    state = WorkerPersistentState(
        symbol_activation_entries={},
        ingest_watermarks={key: watermark_text},
    )
    activation = SymbolActivationSnapshot.from_payload(
        symbol=symbol,
        payload={
            "symbol": symbol,
            "state": "ready_for_serving",
            "visibility": "visible",
            "is_full_backfilled": True,
            "updated_at": "2026-02-24T01:00:00Z",
        },
        fallback_now=now,
    )
    calls = {"run": 0, "health": 0}

    def fake_run_prediction_and_save_outcome(*args, **kwargs):
        calls["run"] += 1
        return SimpleNamespace(
            result=PredictionExecutionResult.OK,
            error=None,
        )

    def fake_upsert_prediction_health(*args, **kwargs):
        calls["health"] += 1
        return {"degraded": False}, False, False

    monkeypatch.setattr(
        "scripts.pipeline_worker.run_prediction_and_save_outcome",
        fake_run_prediction_and_save_outcome,
    )
    monkeypatch.setattr(
        "scripts.pipeline_worker.upsert_prediction_health",
        fake_upsert_prediction_health,
    )

    cycle_predict_gate_skip_counts: dict[str, int] = {}
    _run_publish_timeframe_step(
        write_api=object(),
        query_api=object(),
        symbol=symbol,
        timeframe=timeframe,
        cycle_now=now,
        symbol_activation=activation,
        run_export_stage=False,
        run_predict_stage=True,
        state=state,
        cycle_export_gate_skip_counts={},
        cycle_predict_gate_skip_counts=cycle_predict_gate_skip_counts,
    )

    assert calls == {"run": 1, "health": 1}
    assert cycle_predict_gate_skip_counts == {}


def test_run_publish_timeframe_step_skips_predict_without_ingest_watermark(
    monkeypatch,
):
    symbol = "BTC/USDT"
    timeframe = "1h"
    now = datetime(2026, 2, 24, 1, 0, tzinfo=timezone.utc)
    key = f"{symbol}|{timeframe}"

    state = WorkerPersistentState(
        symbol_activation_entries={},
        ingest_watermarks={},
    )
    activation = SymbolActivationSnapshot.from_payload(
        symbol=symbol,
        payload={
            "symbol": symbol,
            "state": "ready_for_serving",
            "visibility": "visible",
            "is_full_backfilled": True,
            "updated_at": "2026-02-24T01:00:00Z",
        },
        fallback_now=now,
    )
    called = {"run_prediction": False}

    def fail_if_called(*args, **kwargs):
        called["run_prediction"] = True
        raise AssertionError("serial reconcile must skip without ingest watermark")

    monkeypatch.setattr(
        "scripts.pipeline_worker.run_prediction_and_save_outcome",
        fail_if_called,
    )

    cycle_predict_gate_skip_counts: dict[str, int] = {}
    _run_publish_timeframe_step(
        write_api=object(),
        query_api=object(),
        symbol=symbol,
        timeframe=timeframe,
        cycle_now=now,
        symbol_activation=activation,
        run_export_stage=False,
        run_predict_stage=True,
        state=state,
        cycle_export_gate_skip_counts={},
        cycle_predict_gate_skip_counts=cycle_predict_gate_skip_counts,
    )

    assert called["run_prediction"] is False
    assert cycle_predict_gate_skip_counts == {"no_ingest_watermark": 1}


def test_update_full_history_file_uses_full_range_for_long_timeframes(monkeypatch):
    captured_queries: list[str] = []
    sample_df = pd.DataFrame(
        [
            {
                "_time": datetime(2026, 2, 1, 0, 0, tzinfo=timezone.utc),
                "open": 1.0,
                "high": 2.0,
                "low": 0.5,
                "close": 1.5,
                "volume": 10.0,
            }
        ]
    )

    class FakeQueryAPI:
        def query_data_frame(self, query: str):
            captured_queries.append(query)
            return sample_df.copy()

    monkeypatch.setattr(
        "scripts.pipeline_worker.export_ops.save_history_to_json",
        lambda ctx, df, symbol, timeframe: None,
    )

    query_api = FakeQueryAPI()
    assert update_full_history_file(query_api, "BTC/USDT", "1d") is True
    assert "|> range(start: 0)" in captured_queries[0]


def test_update_full_history_file_keeps_lookback_range_for_1h(monkeypatch):
    captured_queries: list[str] = []
    sample_df = pd.DataFrame(
        [
            {
                "_time": datetime(2026, 2, 1, 0, 0, tzinfo=timezone.utc),
                "open": 1.0,
                "high": 2.0,
                "low": 0.5,
                "close": 1.5,
                "volume": 10.0,
            }
        ]
    )

    class FakeQueryAPI:
        def query_data_frame(self, query: str):
            captured_queries.append(query)
            return sample_df.copy()

    monkeypatch.setattr(
        "scripts.pipeline_worker.export_ops.save_history_to_json",
        lambda ctx, df, symbol, timeframe: None,
    )

    query_api = FakeQueryAPI()
    assert update_full_history_file(query_api, "BTC/USDT", "1h") is True
    assert "|> range(start: -30d)" in captured_queries[0]
