import json
from datetime import datetime, timezone

from utils.ingest_state import IngestStateStore


def _utc(year: int, month: int, day: int, hour: int) -> datetime:
    return datetime(year, month, day, hour, 0, 0, tzinfo=timezone.utc)


def test_ingest_state_persists_cursor_per_symbol_and_timeframe(tmp_path):
    state_path = tmp_path / "ingest_state.json"
    store = IngestStateStore(state_path)

    store.upsert("BTC/USDT", "1h", last_closed_ts=_utc(2026, 2, 12, 10), status="ok")
    store.upsert("BTC/USDT", "4h", last_closed_ts=_utc(2026, 2, 12, 8), status="ok")
    store.upsert("ETH/USDT", "1h", last_closed_ts=_utc(2026, 2, 12, 9), status="ok")

    reloaded = IngestStateStore(state_path)
    assert reloaded.get_last_closed("BTC/USDT", "1h") == _utc(2026, 2, 12, 10)
    assert reloaded.get_last_closed("BTC/USDT", "4h") == _utc(2026, 2, 12, 8)
    assert reloaded.get_last_closed("ETH/USDT", "1h") == _utc(2026, 2, 12, 9)


def test_ingest_state_keeps_previous_cursor_when_last_closed_is_none(tmp_path):
    state_path = tmp_path / "ingest_state.json"
    store = IngestStateStore(state_path)
    store.upsert("BTC/USDT", "1h", last_closed_ts=_utc(2026, 2, 12, 10), status="ok")
    store.upsert("BTC/USDT", "1h", last_closed_ts=None, status="failed")

    reloaded = IngestStateStore(state_path)
    entry = reloaded.get("BTC/USDT", "1h")
    assert entry is not None
    assert entry.last_closed_ts == _utc(2026, 2, 12, 10)
    assert entry.status == "failed"


def test_ingest_state_recovers_from_corrupted_file(tmp_path):
    state_path = tmp_path / "ingest_state.json"
    state_path.write_text("{not-valid-json")

    store = IngestStateStore(state_path)
    assert store.get_last_closed("BTC/USDT", "1h") is None

    store.upsert("BTC/USDT", "1h", last_closed_ts=_utc(2026, 2, 12, 10), status="ok")

    payload = json.loads(state_path.read_text())
    assert payload["entries"]["BTC/USDT|1h"]["last_closed_ts"] == "2026-02-12T10:00:00Z"
