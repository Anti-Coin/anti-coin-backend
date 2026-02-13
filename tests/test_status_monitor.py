import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

from scripts.status_monitor import (
    _parse_positive_int_env,
    apply_influx_json_consistency,
    detect_alert_event,
    detect_realert_event,
    evaluate_symbol_timeframe,
    get_latest_ohlcv_timestamp,
    run_monitor_cycle,
    update_status_cycle_counter,
)


def _write_prediction(
    root: Path, symbol: str, updated_at: str, timeframe: str | None = None
) -> None:
    safe = symbol.replace("/", "_")
    if timeframe:
        path = root / f"prediction_{safe}_{timeframe}.json"
    else:
        path = root / f"prediction_{safe}.json"
    path.write_text(json.dumps({"symbol": symbol, "updated_at": updated_at}))


def test_evaluate_symbol_timeframe_fresh_from_legacy_file(tmp_path):
    now = datetime(2026, 2, 10, 12, 0, tzinfo=timezone.utc)
    _write_prediction(tmp_path, "BTC/USDT", "2026-02-10T11:55:00Z")

    snapshot = evaluate_symbol_timeframe(
        symbol="BTC/USDT",
        timeframe="1h",
        now=now,
        static_dir=tmp_path,
        soft_thresholds={"1h": timedelta(minutes=10)},
        hard_thresholds={"1h": timedelta(minutes=20)},
    )

    assert snapshot.status == "fresh"
    assert snapshot.updated_at == "2026-02-10T11:55:00Z"


def test_evaluate_symbol_timeframe_prefers_timeframe_file_over_legacy(tmp_path):
    now = datetime(2026, 2, 10, 12, 0, tzinfo=timezone.utc)
    _write_prediction(tmp_path, "BTC/USDT", "2026-02-10T11:30:00Z")
    _write_prediction(tmp_path, "BTC/USDT", "2026-02-10T11:55:00Z", timeframe="1h")

    snapshot = evaluate_symbol_timeframe(
        symbol="BTC/USDT",
        timeframe="1h",
        now=now,
        static_dir=tmp_path,
        soft_thresholds={"1h": timedelta(minutes=10)},
        hard_thresholds={"1h": timedelta(minutes=20)},
    )

    assert snapshot.status == "fresh"
    assert snapshot.detail == "checked=prediction_BTC_USDT_1h.json"


def test_evaluate_symbol_timeframe_corrupt_when_json_invalid(tmp_path):
    (tmp_path / "prediction_BTC_USDT.json").write_text("{invalid-json")
    snapshot = evaluate_symbol_timeframe("BTC/USDT", "1h", static_dir=tmp_path)
    assert snapshot.status == "corrupt"


def test_evaluate_symbol_timeframe_hard_stale(tmp_path):
    now = datetime(2026, 2, 10, 12, 0, tzinfo=timezone.utc)
    _write_prediction(tmp_path, "BTC/USDT", "2026-02-10T11:30:00Z")

    snapshot = evaluate_symbol_timeframe(
        symbol="BTC/USDT",
        timeframe="1h",
        now=now,
        static_dir=tmp_path,
        soft_thresholds={"1h": timedelta(minutes=10)},
        hard_thresholds={"1h": timedelta(minutes=20)},
    )

    assert snapshot.status == "hard_stale"
    assert snapshot.age_minutes == 30.0


def test_detect_alert_event_only_for_unhealthy_transitions_and_recovery():
    assert detect_alert_event(None, "fresh") is None
    assert detect_alert_event("fresh", "stale") is None
    assert detect_alert_event("fresh", "hard_stale") == "hard_stale"
    assert detect_alert_event("fresh", "missing") == "missing"
    assert detect_alert_event("hard_stale", "hard_stale") is None
    assert detect_alert_event("hard_stale", "corrupt") == "corrupt"
    assert detect_alert_event("corrupt", "stale") == "recovery"
    assert detect_alert_event("corrupt", "missing") == "missing"
    assert detect_alert_event("missing", "stale") == "recovery"


def test_detect_realert_event_for_hard_and_soft_statuses(monkeypatch):
    monkeypatch.setattr("scripts.status_monitor.MONITOR_RE_ALERT_CYCLES", 3)

    assert detect_realert_event("hard_stale", 1) is None
    assert detect_realert_event("hard_stale", 2) is None
    assert detect_realert_event("hard_stale", 3) == "hard_stale_repeat"
    assert detect_realert_event("hard_stale", 4) is None
    assert detect_realert_event("hard_stale", 6) == "hard_stale_repeat"

    assert detect_realert_event("stale", 2) is None
    assert detect_realert_event("stale", 3) == "soft_stale_repeat"
    assert detect_realert_event("stale", 6) == "soft_stale_repeat"
    assert detect_realert_event("fresh", 6) is None


def test_update_status_cycle_counter_resets_on_status_change():
    counters: dict[str, dict[str, str | int]] = {}
    key = "BTC/USDT|1h"

    assert update_status_cycle_counter(counters, key, "stale") == 1
    assert update_status_cycle_counter(counters, key, "stale") == 2
    assert update_status_cycle_counter(counters, key, "stale") == 3
    assert update_status_cycle_counter(counters, key, "fresh") == 1
    assert update_status_cycle_counter(counters, key, "fresh") == 2


def test_run_monitor_cycle_deduplicates_and_emits_recovery(tmp_path):
    state = {}
    status_counters = {}
    symbol = "BTC/USDT"
    now = datetime(2026, 2, 10, 12, 0, tzinfo=timezone.utc)

    _write_prediction(tmp_path, symbol, "2026-02-10T11:30:00Z")
    events = run_monitor_cycle(
        state=state,
        status_counters=status_counters,
        now=now,
        symbols=[symbol],
        timeframes=["1h"],
        static_dir=tmp_path,
        soft_thresholds={"1h": timedelta(minutes=10)},
        hard_thresholds={"1h": timedelta(minutes=20)},
    )
    assert [e.event for e in events] == ["hard_stale"]

    events = run_monitor_cycle(
        state=state,
        status_counters=status_counters,
        now=now,
        symbols=[symbol],
        timeframes=["1h"],
        static_dir=tmp_path,
        soft_thresholds={"1h": timedelta(minutes=10)},
        hard_thresholds={"1h": timedelta(minutes=20)},
    )
    assert events == []

    _write_prediction(tmp_path, symbol, "2026-02-10T11:58:00Z")
    events = run_monitor_cycle(
        state=state,
        status_counters=status_counters,
        now=now,
        symbols=[symbol],
        timeframes=["1h"],
        static_dir=tmp_path,
        soft_thresholds={"1h": timedelta(minutes=10)},
        hard_thresholds={"1h": timedelta(minutes=20)},
    )
    assert [e.event for e in events] == ["recovery"]


def test_run_monitor_cycle_realerts_on_repeated_hard_stale(tmp_path, monkeypatch):
    monkeypatch.setattr("scripts.status_monitor.MONITOR_RE_ALERT_CYCLES", 3)
    state = {}
    status_counters = {}
    symbol = "BTC/USDT"
    now = datetime(2026, 2, 10, 12, 0, tzinfo=timezone.utc)

    _write_prediction(tmp_path, symbol, "2026-02-10T11:30:00Z")

    events = run_monitor_cycle(
        state=state,
        status_counters=status_counters,
        now=now,
        symbols=[symbol],
        timeframes=["1h"],
        static_dir=tmp_path,
        soft_thresholds={"1h": timedelta(minutes=10)},
        hard_thresholds={"1h": timedelta(minutes=20)},
    )
    assert [e.event for e in events] == ["hard_stale"]

    events = run_monitor_cycle(
        state=state,
        status_counters=status_counters,
        now=now,
        symbols=[symbol],
        timeframes=["1h"],
        static_dir=tmp_path,
        soft_thresholds={"1h": timedelta(minutes=10)},
        hard_thresholds={"1h": timedelta(minutes=20)},
    )
    assert events == []

    events = run_monitor_cycle(
        state=state,
        status_counters=status_counters,
        now=now,
        symbols=[symbol],
        timeframes=["1h"],
        static_dir=tmp_path,
        soft_thresholds={"1h": timedelta(minutes=10)},
        hard_thresholds={"1h": timedelta(minutes=20)},
    )
    assert [e.event for e in events] == ["hard_stale_repeat"]
    assert events[0].cycles_in_status == 3


def test_run_monitor_cycle_realerts_on_repeated_soft_stale(tmp_path, monkeypatch):
    monkeypatch.setattr("scripts.status_monitor.MONITOR_RE_ALERT_CYCLES", 3)
    state = {}
    status_counters = {}
    symbol = "BTC/USDT"
    now = datetime(2026, 2, 10, 12, 0, tzinfo=timezone.utc)

    _write_prediction(tmp_path, symbol, "2026-02-10T11:50:00Z")

    events = run_monitor_cycle(
        state=state,
        status_counters=status_counters,
        now=now,
        symbols=[symbol],
        timeframes=["1h"],
        static_dir=tmp_path,
        soft_thresholds={"1h": timedelta(minutes=5)},
        hard_thresholds={"1h": timedelta(minutes=20)},
    )
    assert events == []

    events = run_monitor_cycle(
        state=state,
        status_counters=status_counters,
        now=now,
        symbols=[symbol],
        timeframes=["1h"],
        static_dir=tmp_path,
        soft_thresholds={"1h": timedelta(minutes=5)},
        hard_thresholds={"1h": timedelta(minutes=20)},
    )
    assert events == []

    events = run_monitor_cycle(
        state=state,
        status_counters=status_counters,
        now=now,
        symbols=[symbol],
        timeframes=["1h"],
        static_dir=tmp_path,
        soft_thresholds={"1h": timedelta(minutes=5)},
        hard_thresholds={"1h": timedelta(minutes=20)},
    )
    assert [e.event for e in events] == ["soft_stale_repeat"]
    assert events[0].cycles_in_status == 3


def test_parse_positive_int_env_returns_default_on_invalid(monkeypatch):
    monkeypatch.setenv("MONITOR_POLL_SECONDS", "not-int")
    assert _parse_positive_int_env("MONITOR_POLL_SECONDS", 60) == 60


def test_parse_positive_int_env_returns_value_when_valid(monkeypatch):
    monkeypatch.setenv("MONITOR_POLL_SECONDS", "15")
    assert _parse_positive_int_env("MONITOR_POLL_SECONDS", 60) == 15


class _FakeRecord:
    def __init__(self, dt: datetime):
        self._dt = dt

    def get_time(self) -> datetime:
        return self._dt


class _FakeTable:
    def __init__(self, records: list[_FakeRecord]):
        self.records = records


class _FakeQueryApi:
    def __init__(self, latest_by_symbol: dict[str, datetime | list[datetime] | None]):
        self._latest_by_symbol = latest_by_symbol

    def query(self, query: str):
        marker = 'r["symbol"] == "'
        start = query.find(marker)
        if start < 0:
            return []
        start += len(marker)
        end = query.find('"', start)
        symbol = query[start:end]
        latest = self._latest_by_symbol.get(symbol)
        if latest is None:
            return []
        if isinstance(latest, list):
            return [_FakeTable([_FakeRecord(dt)]) for dt in latest]
        return [_FakeTable([_FakeRecord(latest)])]


def test_get_latest_ohlcv_timestamp_returns_latest_value(monkeypatch):
    monkeypatch.setattr("scripts.status_monitor.INFLUXDB_BUCKET", "market_data")
    query_api = _FakeQueryApi(
        {"BTC/USDT": datetime(2026, 2, 10, 11, 0, tzinfo=timezone.utc)}
    )

    latest = get_latest_ohlcv_timestamp(query_api, "BTC/USDT")
    assert latest == datetime(2026, 2, 10, 11, 0, tzinfo=timezone.utc)


def test_get_latest_ohlcv_timestamp_uses_max_across_tables(monkeypatch):
    monkeypatch.setattr("scripts.status_monitor.INFLUXDB_BUCKET", "market_data")
    query_api = _FakeQueryApi(
        {
            "BTC/USDT": [
                datetime(2026, 2, 10, 10, 0, tzinfo=timezone.utc),
                datetime(2026, 2, 10, 11, 30, tzinfo=timezone.utc),
            ]
        }
    )

    latest = get_latest_ohlcv_timestamp(query_api, "BTC/USDT")
    assert latest == datetime(2026, 2, 10, 11, 30, tzinfo=timezone.utc)


def test_run_monitor_cycle_marks_hard_stale_when_influx_json_gap_exceeds_limit(
    tmp_path, monkeypatch
):
    monkeypatch.setattr("scripts.status_monitor.INFLUXDB_BUCKET", "market_data")
    now = datetime(2026, 2, 10, 12, 0, tzinfo=timezone.utc)
    _write_prediction(tmp_path, "BTC/USDT", "2026-02-10T12:00:00Z")
    query_api = _FakeQueryApi(
        {"BTC/USDT": datetime(2026, 2, 10, 10, 0, tzinfo=timezone.utc)}
    )

    state = {}
    events = run_monitor_cycle(
        state=state,
        now=now,
        symbols=["BTC/USDT"],
        timeframes=["1h"],
        static_dir=tmp_path,
        soft_thresholds={"1h": timedelta(minutes=10)},
        hard_thresholds={"1h": timedelta(minutes=30)},
        query_api=query_api,
    )

    assert [e.event for e in events] == ["hard_stale"]
    snapshot = state["BTC/USDT|1h"]
    assert snapshot.status == "hard_stale"
    assert "influx_json_mismatch" in snapshot.detail


def test_apply_influx_json_consistency_keeps_status_when_gap_within_limit(
    tmp_path,
):
    now = datetime(2026, 2, 10, 12, 0, tzinfo=timezone.utc)
    _write_prediction(tmp_path, "BTC/USDT", "2026-02-10T12:00:00Z")
    snapshot = evaluate_symbol_timeframe(
        symbol="BTC/USDT",
        timeframe="1h",
        now=now,
        static_dir=tmp_path,
        soft_thresholds={"1h": timedelta(minutes=10)},
        hard_thresholds={"1h": timedelta(minutes=30)},
    )
    latest_ohlcv_ts = datetime(2026, 2, 10, 11, 40, tzinfo=timezone.utc)

    checked = apply_influx_json_consistency(snapshot, latest_ohlcv_ts)
    assert checked.status == snapshot.status
    assert checked.detail == snapshot.detail
