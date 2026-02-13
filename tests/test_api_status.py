import json
from datetime import datetime, timedelta, timezone

import pytest
from fastapi import HTTPException

import api.main as api_main


def _write_prediction_file(
    tmp_path,
    symbol: str,
    payload: dict,
    timeframe: str = "1h",
    *,
    legacy: bool = False,
) -> None:
    safe_symbol = symbol.replace("/", "_")
    if legacy:
        path = tmp_path / f"prediction_{safe_symbol}.json"
    else:
        path = tmp_path / f"prediction_{safe_symbol}_{timeframe}.json"
    path.write_text(json.dumps(payload))


def _write_prediction_health_file(tmp_path, entries: dict) -> None:
    path = tmp_path / "prediction_health.json"
    path.write_text(
        json.dumps(
            {
                "version": 1,
                "updated_at": datetime.now(timezone.utc).strftime(
                    "%Y-%m-%dT%H:%M:%SZ"
                ),
                "entries": entries,
            }
        )
    )


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


def test_check_status_returns_503_for_invalid_updated_at_format(
    tmp_path, monkeypatch
):
    monkeypatch.setattr(api_main, "STATIC_DIR", tmp_path)
    _write_prediction_file(tmp_path, "BTC/USDT", {"updated_at": "bad-format"})

    with pytest.raises(HTTPException) as exc:
        api_main.check_status("BTC/USDT")

    assert exc.value.status_code == 503
    assert exc.value.detail == "Invalid data format"


def test_check_status_returns_fresh_state(tmp_path, monkeypatch):
    monkeypatch.setattr(api_main, "STATIC_DIR", tmp_path)
    monkeypatch.setattr(
        api_main, "PREDICTION_HEALTH_FILE", tmp_path / "prediction_health.json"
    )
    monkeypatch.setattr(
        api_main, "FRESHNESS_THRESHOLDS", {"1h": timedelta(minutes=10)}
    )
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
    assert response["degraded"] is False
    assert response["prediction_failure_count"] == 0
    assert "warning" not in response


def test_check_status_returns_stale_with_warning_in_soft_window(
    tmp_path, monkeypatch
):
    monkeypatch.setattr(api_main, "STATIC_DIR", tmp_path)
    monkeypatch.setattr(
        api_main, "PREDICTION_HEALTH_FILE", tmp_path / "prediction_health.json"
    )
    monkeypatch.setattr(
        api_main, "FRESHNESS_THRESHOLDS", {"1h": timedelta(minutes=1)}
    )
    monkeypatch.setattr(
        api_main, "FRESHNESS_HARD_THRESHOLDS", {"1h": timedelta(minutes=3)}
    )

    updated_at = datetime.now(timezone.utc) - timedelta(minutes=2)
    _write_prediction_file(
        tmp_path,
        "BTC/USDT",
        {"updated_at": updated_at.strftime("%Y-%m-%dT%H:%M:%SZ")},
    )
    response = api_main.check_status("BTC/USDT")

    assert response["status"] == "stale"
    assert response["degraded"] is False
    assert "warning" in response


def test_check_status_returns_503_beyond_hard_limit(tmp_path, monkeypatch):
    monkeypatch.setattr(api_main, "STATIC_DIR", tmp_path)
    monkeypatch.setattr(
        api_main, "FRESHNESS_THRESHOLDS", {"1h": timedelta(minutes=1)}
    )
    monkeypatch.setattr(
        api_main, "FRESHNESS_HARD_THRESHOLDS", {"1h": timedelta(minutes=2)}
    )

    updated_at = datetime.now(timezone.utc) - timedelta(minutes=3)
    _write_prediction_file(
        tmp_path,
        "BTC/USDT",
        {"updated_at": updated_at.strftime("%Y-%m-%dT%H:%M:%SZ")},
    )

    with pytest.raises(HTTPException) as exc:
        api_main.check_status("BTC/USDT")

    assert exc.value.status_code == 503
    assert "hard limit" in exc.value.detail


def test_check_status_uses_1h_threshold_as_fallback(tmp_path, monkeypatch):
    monkeypatch.setattr(api_main, "STATIC_DIR", tmp_path)
    monkeypatch.setattr(
        api_main, "FRESHNESS_THRESHOLDS", {"1h": timedelta(minutes=1)}
    )
    monkeypatch.setattr(
        api_main, "FRESHNESS_HARD_THRESHOLDS", {"1h": timedelta(minutes=3)}
    )

    updated_at = datetime.now(timezone.utc) - timedelta(minutes=2)
    _write_prediction_file(
        tmp_path,
        "BTC/USDT",
        {"updated_at": updated_at.strftime("%Y-%m-%dT%H:%M:%SZ")},
        legacy=True,
    )
    response = api_main.check_status("BTC/USDT", timeframe="unknown")

    assert response["status"] == "stale"


def test_check_status_reads_legacy_prediction_file_as_fallback(
    tmp_path, monkeypatch
):
    monkeypatch.setattr(api_main, "STATIC_DIR", tmp_path)
    monkeypatch.setattr(
        api_main, "FRESHNESS_THRESHOLDS", {"1h": timedelta(minutes=10)}
    )
    monkeypatch.setattr(
        api_main, "FRESHNESS_HARD_THRESHOLDS", {"1h": timedelta(minutes=20)}
    )

    now = datetime.now(timezone.utc)
    _write_prediction_file(
        tmp_path,
        "BTC/USDT",
        {"updated_at": now.strftime("%Y-%m-%dT%H:%M:%SZ")},
        legacy=True,
    )

    response = api_main.check_status("BTC/USDT", timeframe="1h")
    assert response["status"] == "fresh"


def test_check_status_exposes_degraded_state_from_prediction_health(
    tmp_path, monkeypatch
):
    monkeypatch.setattr(api_main, "STATIC_DIR", tmp_path)
    monkeypatch.setattr(
        api_main, "PREDICTION_HEALTH_FILE", tmp_path / "prediction_health.json"
    )
    monkeypatch.setattr(
        api_main, "FRESHNESS_THRESHOLDS", {"1h": timedelta(minutes=10)}
    )
    monkeypatch.setattr(
        api_main, "FRESHNESS_HARD_THRESHOLDS", {"1h": timedelta(minutes=20)}
    )

    now = datetime.now(timezone.utc)
    _write_prediction_file(
        tmp_path, "BTC/USDT", {"updated_at": now.strftime("%Y-%m-%dT%H:%M:%SZ")}
    )
    _write_prediction_health_file(
        tmp_path,
        {
            "BTC/USDT|1h": {
                "symbol": "BTC/USDT",
                "timeframe": "1h",
                "degraded": True,
                "last_success_at": "2026-02-12T10:00:00Z",
                "last_failure_at": "2026-02-12T10:05:00Z",
                "last_error": "model_missing",
                "consecutive_failures": 3,
            }
        },
    )

    response = api_main.check_status("BTC/USDT")
    assert response["status"] == "fresh"
    assert response["degraded"] is True
    assert response["degraded_reason"] == "model_missing"
    assert response["last_prediction_success_at"] == "2026-02-12T10:00:00Z"
    assert response["last_prediction_failure_at"] == "2026-02-12T10:05:00Z"
    assert response["prediction_failure_count"] == 3


def test_check_status_marks_degraded_when_prediction_health_file_is_corrupted(
    tmp_path, monkeypatch
):
    monkeypatch.setattr(api_main, "STATIC_DIR", tmp_path)
    monkeypatch.setattr(
        api_main, "PREDICTION_HEALTH_FILE", tmp_path / "prediction_health.json"
    )
    monkeypatch.setattr(
        api_main, "FRESHNESS_THRESHOLDS", {"1h": timedelta(minutes=10)}
    )
    monkeypatch.setattr(
        api_main, "FRESHNESS_HARD_THRESHOLDS", {"1h": timedelta(minutes=20)}
    )

    now = datetime.now(timezone.utc)
    _write_prediction_file(
        tmp_path, "BTC/USDT", {"updated_at": now.strftime("%Y-%m-%dT%H:%M:%SZ")}
    )
    (tmp_path / "prediction_health.json").write_text("{not-json")

    response = api_main.check_status("BTC/USDT")
    assert response["status"] == "fresh"
    assert response["degraded"] is True
    assert response["degraded_reason"] == "prediction_health_read_error"
