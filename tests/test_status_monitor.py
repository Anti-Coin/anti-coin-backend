import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

from scripts.status_monitor import (
    _parse_positive_int_env,
    detect_alert_event,
    evaluate_symbol_timeframe,
    run_monitor_cycle,
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
    assert detect_alert_event("hard_stale", "hard_stale") is None
    assert detect_alert_event("hard_stale", "corrupt") == "corrupt"
    assert detect_alert_event("corrupt", "stale") == "recovery"
    assert detect_alert_event("corrupt", "missing") is None


def test_run_monitor_cycle_deduplicates_and_emits_recovery(tmp_path):
    state = {}
    symbol = "BTC/USDT"
    now = datetime(2026, 2, 10, 12, 0, tzinfo=timezone.utc)

    _write_prediction(tmp_path, symbol, "2026-02-10T11:30:00Z")
    events = run_monitor_cycle(
        state=state,
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
        now=now,
        symbols=[symbol],
        timeframes=["1h"],
        static_dir=tmp_path,
        soft_thresholds={"1h": timedelta(minutes=10)},
        hard_thresholds={"1h": timedelta(minutes=20)},
    )
    assert [e.event for e in events] == ["recovery"]


def test_parse_positive_int_env_returns_default_on_invalid(monkeypatch):
    monkeypatch.setenv("MONITOR_POLL_SECONDS", "not-int")
    assert _parse_positive_int_env("MONITOR_POLL_SECONDS", 60) == 60


def test_parse_positive_int_env_returns_value_when_valid(monkeypatch):
    monkeypatch.setenv("MONITOR_POLL_SECONDS", "15")
    assert _parse_positive_int_env("MONITOR_POLL_SECONDS", 60) == 15
