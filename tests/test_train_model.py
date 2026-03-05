import json
import pytest
import pandas as pd
from pathlib import Path
from types import SimpleNamespace

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


def test_resolve_model_paths_primary_skips_legacy_path():
    canonical, legacy = train_model._resolve_model_paths("BTC/USDT", "1h")

    assert canonical.name == "model_BTC_USDT_1h.json"
    assert legacy is None


def test_resolve_model_paths_non_primary_skips_legacy_path():
    canonical, legacy = train_model._resolve_model_paths("BTC/USDT", "1d")

    assert canonical.name == "model_BTC_USDT_1d.json"
    assert legacy is None


def test_resolve_model_metadata_paths_primary_skips_legacy_path():
    canonical, legacy = train_model._resolve_model_metadata_paths("BTC/USDT", "1h")

    assert canonical.name == "model_BTC_USDT_1h.meta.json"
    assert legacy is None


def test_resolve_model_metadata_paths_non_primary_skips_legacy_path():
    canonical, legacy = train_model._resolve_model_metadata_paths("BTC/USDT", "1d")

    assert canonical.name == "model_BTC_USDT_1d.meta.json"
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


def test_prepare_prophet_train_df_converts_timezone_aware_ds_to_naive_utc():
    df = pd.DataFrame(
        {
            "timestamp": pd.to_datetime(
                ["2026-02-26T00:00:00Z", "2026-02-26T01:00:00Z"], utc=True
            ),
            "close": [100.0, 101.0],
        }
    )

    train_df = train_model._prepare_prophet_train_df(df)

    assert list(train_df.columns) == ["ds", "y"]
    assert train_df["ds"].dt.tz is None
    assert str(train_df["ds"].dtype) == "datetime64[ns]"


def test_train_and_save_persists_model_metadata_schema(tmp_path, monkeypatch):
    models_dir = tmp_path / "models"
    static_dir = tmp_path / "static_data"
    models_dir.mkdir(parents=True, exist_ok=True)
    static_dir.mkdir(parents=True, exist_ok=True)

    snapshot_path = tmp_path / "snapshot.parquet"
    pd.DataFrame(
        {
            "timestamp": pd.to_datetime(
                ["2026-02-26T00:00:00Z", "2026-02-26T01:00:00Z"], utc=True
            ),
            "close": [100.0, 101.0],
        }
    ).to_parquet(snapshot_path, index=False)

    monkeypatch.setattr(train_model, "MODELS_DIR", models_dir)
    monkeypatch.setattr(train_model, "STATIC_DIR", static_dir)
    monkeypatch.setattr(
        train_model,
        "extract_ohlcv_to_parquet",
        lambda *args, **kwargs: snapshot_path,
    )

    class DummyProphet:
        def __init__(self, daily_seasonality=True):
            self.daily_seasonality = daily_seasonality
            self.fitted = False

        def fit(self, df):
            self.fitted = True
            self.fit_input = df.copy()

    monkeypatch.setattr(train_model, "Prophet", DummyProphet)
    monkeypatch.setattr(
        train_model,
        "model_to_json",
        lambda model: "{\"model\":\"serialized\"}",
    )

    class DummyRunContext:
        def __enter__(self):
            return SimpleNamespace(info=SimpleNamespace(run_id="run-123"))

        def __exit__(self, exc_type, exc, tb):
            return False

    class DummyMlflow:
        def start_run(self, run_name=None):
            return DummyRunContext()

        def log_params(self, params):
            return None

        def log_metric(self, key, value):
            return None

        def log_dict(self, payload, artifact_file):
            return None

        def set_tag(self, key, value):
            return None

        def log_param(self, key, value):
            return None

        def log_artifact(self, local_path, artifact_path=None):
            return None

    result = train_model.train_and_save(
        "BTC/USDT",
        "1h",
        lookback_limit=10,
        client=object(),
        mlflow=DummyMlflow(),
    )

    metadata_path = models_dir / "model_BTC_USDT_1h.meta.json"
    assert metadata_path.exists()

    payload = json.loads(metadata_path.read_text())
    assert payload["schema_version"] == 1
    assert payload["symbol"] == "BTC/USDT"
    assert payload["timeframe"] == "1h"
    assert payload["run_id"] == "run-123"
    assert payload["row_count"] == 2
    assert payload["data_range"]["start"] == "2026-02-26T00:00:00Z"
    assert payload["data_range"]["end"] == "2026-02-26T01:00:00Z"
    assert payload["snapshot_path"] == str(snapshot_path)
    assert payload["status"] == "ok"
    assert payload["trained_at"].endswith("Z")
    assert payload["model_version"] == result["model_version"]
    assert not (models_dir / "model_BTC_USDT.json").exists()
    assert not (models_dir / "model_BTC_USDT.meta.json").exists()
