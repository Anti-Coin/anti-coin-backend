import pytest
from pathlib import Path

from scripts import train_model


def test_parse_csv_uses_default_when_empty_or_none():
    defaults = ["BTC/USDT", "ETH/USDT"]
    assert train_model._parse_csv(None, default=defaults) == defaults
    assert train_model._parse_csv("", default=defaults) == defaults
    assert train_model._parse_csv(" , ", default=defaults) == defaults


def test_parse_csv_trims_and_filters_empty_tokens():
    parsed = train_model._parse_csv(
        " BTC/USDT, ,ETH/USDT ,, SOL/USDT ", default=["XRP/USDT"]
    )
    assert parsed == ["BTC/USDT", "ETH/USDT", "SOL/USDT"]


@pytest.mark.parametrize("limit", [0, -1, -100])
def test_require_positive_limit_rejects_non_positive(limit):
    with pytest.raises(ValueError):
        train_model._require_positive_limit(limit)


def test_parse_env_int_falls_back_to_default(monkeypatch):
    monkeypatch.delenv("TRAIN_LOOKBACK_LIMIT", raising=False)
    assert train_model._parse_env_int("TRAIN_LOOKBACK_LIMIT", default=500) == 500

    monkeypatch.setenv("TRAIN_LOOKBACK_LIMIT", "700")
    assert train_model._parse_env_int("TRAIN_LOOKBACK_LIMIT", default=500) == 700

    monkeypatch.setenv("TRAIN_LOOKBACK_LIMIT", "not-int")
    assert train_model._parse_env_int("TRAIN_LOOKBACK_LIMIT", default=500) == 500


def test_resolve_model_paths_primary_writes_legacy_path():
    canonical, legacy = train_model._resolve_model_paths("BTC/USDT", "1h")

    assert canonical.name == "model_BTC_USDT_1h.json"
    assert legacy is not None
    assert legacy.name == "model_BTC_USDT.json"


def test_resolve_model_paths_non_primary_skips_legacy_path():
    canonical, legacy = train_model._resolve_model_paths("BTC/USDT", "1d")

    assert canonical.name == "model_BTC_USDT_1d.json"
    assert legacy is None


def test_main_returns_error_code_for_invalid_limit():
    rc = train_model.main(["--lookback-limit", "0"])
    assert rc == 2


def test_main_builds_training_plan_and_runs_job(monkeypatch):
    captured = {}

    def fake_run_training_job(*, symbols, timeframes, lookback_limit):
        captured["symbols"] = symbols
        captured["timeframes"] = timeframes
        captured["lookback_limit"] = lookback_limit
        return {"failed": 0}

    monkeypatch.setattr(train_model, "run_training_job", fake_run_training_job)

    rc = train_model.main(
        [
            "--symbols",
            "BTC/USDT,ETH/USDT",
            "--timeframes",
            "1h,1d",
            "--lookback-limit",
            "123",
        ]
    )

    assert rc == 0
    assert captured == {
        "symbols": ["BTC/USDT", "ETH/USDT"],
        "timeframes": ["1h", "1d"],
        "lookback_limit": 123,
    }


def test_resolve_mlflow_tracking_uri_defaults_to_sqlite(monkeypatch):
    monkeypatch.delenv("MLFLOW_TRACKING_URI", raising=False)
    uri = train_model._resolve_mlflow_tracking_uri()
    expected = f"sqlite:///{Path(train_model.STATIC_DIR) / 'mlflow.db'}"
    assert uri == expected


def test_main_returns_error_when_training_has_partial_failure(monkeypatch):
    monkeypatch.setattr(
        train_model,
        "run_training_job",
        lambda **kwargs: {"failed": 1},
    )
    rc = train_model.main(["--symbols", "BTC/USDT", "--timeframes", "1h"])
    assert rc == 1


def test_run_training_job_allows_partial_success(monkeypatch):
    class DummyClient:
        def close(self):
            return None

    class DummyMlflow:
        def __init__(self):
            self.uri = None
            self.experiment = None

        def set_tracking_uri(self, uri):
            self.uri = uri

        def set_experiment(self, name):
            self.experiment = name

    call_state = {"count": 0}

    def fake_train_and_save(*args, **kwargs):
        call_state["count"] += 1
        symbol = args[0]
        if symbol == "ETH/USDT":
            raise RuntimeError("train failed")
        return {"status": "ok"}

    monkeypatch.setattr(train_model, "_get_influx_client", lambda: DummyClient())
    monkeypatch.setattr(train_model, "_load_mlflow_module", lambda: DummyMlflow())
    monkeypatch.setattr(train_model, "train_and_save", fake_train_and_save)

    summary = train_model.run_training_job(
        symbols=["BTC/USDT", "ETH/USDT"],
        timeframes=["1h"],
        lookback_limit=10,
    )

    assert call_state["count"] == 2
    assert summary["total"] == 2
    assert summary["succeeded"] == 1
    assert summary["failed"] == 1
    assert summary["failures"][0]["symbol"] == "ETH/USDT"
