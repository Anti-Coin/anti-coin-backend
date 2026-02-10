import json
from datetime import datetime, timedelta, timezone

import pytest
from fastapi import HTTPException

import api.main as api_main


def _write_prediction_file(tmp_path, symbol: str, payload: dict) -> None:
    safe_symbol = symbol.replace("/", "_")
    path = tmp_path / f"prediction_{safe_symbol}.json"
    path.write_text(json.dumps(payload))


def test_check_status_returns_503_when_file_is_missing(tmp_path, monkeypatch):
    monkeypatch.setattr(api_main, "STATIC_DIR", tmp_path)

    with pytest.raises(HTTPException) as exc:
        api_main.check_status("BTC/USDT")

    assert exc.value.status_code == 503
    assert exc.value.detail == "Not initialized yet."


def test_check_status_returns_503_on_corrupted_json(tmp_path, monkeypatch):
    monkeypatch.setattr(api_main, "STATIC_DIR", tmp_path)
    path = tmp_path / "prediction_BTC_USDT.json"
    path.write_text("{this-is-not-json")

    with pytest.raises(HTTPException) as exc:
        api_main.check_status("BTC/USDT")

    assert exc.value.status_code == 503
    assert exc.value.detail == "Data corruption detected"


def test_check_status_returns_503_for_invalid_updated_at_format(tmp_path, monkeypatch):
    monkeypatch.setattr(api_main, "STATIC_DIR", tmp_path)
    _write_prediction_file(tmp_path, "BTC/USDT", {"updated_at": "bad-format"})

    with pytest.raises(HTTPException) as exc:
        api_main.check_status("BTC/USDT")

    assert exc.value.status_code == 503
    assert exc.value.detail == "Invalid data format"


def test_check_status_returns_fresh_state(tmp_path, monkeypatch):
    monkeypatch.setattr(api_main, "STATIC_DIR", tmp_path)
    monkeypatch.setattr(api_main, "FRESHNESS_THRESHOLDS", {"1h": timedelta(minutes=10)})
    monkeypatch.setattr(
        api_main, "FRESHNESS_HARD_THRESHOLDS", {"1h": timedelta(minutes=20)}
    )

    now = datetime.now(timezone.utc)
    _write_prediction_file(
        tmp_path, "BTC/USDT", {"updated_at": now.strftime("%Y-%m-%dT%H:%M:%SZ")}
    )
    response = api_main.check_status("BTC/USDT")

    assert response["status"] == "fresh"
    assert response["threshold_minutes"] == {"soft": 10, "hard": 20}
    assert "warning" not in response


def test_check_status_returns_stale_with_warning_in_soft_window(tmp_path, monkeypatch):
    monkeypatch.setattr(api_main, "STATIC_DIR", tmp_path)
    monkeypatch.setattr(api_main, "FRESHNESS_THRESHOLDS", {"1h": timedelta(minutes=1)})
    monkeypatch.setattr(
        api_main, "FRESHNESS_HARD_THRESHOLDS", {"1h": timedelta(minutes=3)}
    )

    updated_at = datetime.now(timezone.utc) - timedelta(minutes=2)
    _write_prediction_file(
        tmp_path, "BTC/USDT", {"updated_at": updated_at.strftime("%Y-%m-%dT%H:%M:%SZ")}
    )
    response = api_main.check_status("BTC/USDT")

    assert response["status"] == "stale"
    assert "warning" in response


def test_check_status_returns_503_beyond_hard_limit(tmp_path, monkeypatch):
    monkeypatch.setattr(api_main, "STATIC_DIR", tmp_path)
    monkeypatch.setattr(api_main, "FRESHNESS_THRESHOLDS", {"1h": timedelta(minutes=1)})
    monkeypatch.setattr(
        api_main, "FRESHNESS_HARD_THRESHOLDS", {"1h": timedelta(minutes=2)}
    )

    updated_at = datetime.now(timezone.utc) - timedelta(minutes=3)
    _write_prediction_file(
        tmp_path, "BTC/USDT", {"updated_at": updated_at.strftime("%Y-%m-%dT%H:%M:%SZ")}
    )

    with pytest.raises(HTTPException) as exc:
        api_main.check_status("BTC/USDT")

    assert exc.value.status_code == 503
    assert "hard limit" in exc.value.detail


def test_check_status_uses_1h_threshold_as_fallback(tmp_path, monkeypatch):
    monkeypatch.setattr(api_main, "STATIC_DIR", tmp_path)
    monkeypatch.setattr(api_main, "FRESHNESS_THRESHOLDS", {"1h": timedelta(minutes=1)})
    monkeypatch.setattr(
        api_main, "FRESHNESS_HARD_THRESHOLDS", {"1h": timedelta(minutes=3)}
    )

    updated_at = datetime.now(timezone.utc) - timedelta(minutes=2)
    _write_prediction_file(
        tmp_path, "BTC/USDT", {"updated_at": updated_at.strftime("%Y-%m-%dT%H:%M:%SZ")}
    )
    response = api_main.check_status("BTC/USDT", timeframe="unknown")

    assert response["status"] == "stale"
