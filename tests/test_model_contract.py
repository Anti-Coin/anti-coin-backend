import json

import pandas as pd

from scripts import pipeline_worker, train_model
from workers import predict as predict_ops


def test_fit_contract_normalizes_ds_to_timezone_naive():
    source = pd.DataFrame(
        {
            "timestamp": pd.to_datetime(
                ["2026-02-26T00:00:00Z", "2026-02-26T01:00:00Z"], utc=True
            ),
            "close": [100.0, 101.0],
        }
    )

    train_df = train_model._prepare_prophet_train_df(source)

    assert list(train_df.columns) == ["ds", "y"]
    assert train_df["ds"].dt.tz is None
    assert str(train_df["ds"].dtype) == "datetime64[ns]"
    assert train_df["y"].tolist() == [100.0, 101.0]


def test_predict_contract_uses_canonical_model_and_writes_json_and_influx(
    tmp_path, monkeypatch
):
    models_dir = tmp_path / "models"
    static_dir = tmp_path / "static_data"
    models_dir.mkdir(parents=True, exist_ok=True)

    canonical_model = models_dir / "model_BTC_USDT_1h.json"
    legacy_model = models_dir / "model_BTC_USDT.json"
    canonical_model.write_text("canonical-json")
    legacy_model.write_text("legacy-json")

    loaded_payloads: list[str] = []

    class FakeModel:
        def predict(self, future: pd.DataFrame) -> pd.DataFrame:
            assert list(future.columns) == ["ds"]
            assert future["ds"].dt.tz is None
            result = future.copy()
            result["yhat"] = 1.0
            result["yhat_lower"] = 0.5
            result["yhat_upper"] = 1.5
            return result

    fake_model = FakeModel()

    def fake_model_from_json(raw: str):
        loaded_payloads.append(raw)
        return fake_model

    class FakeWriteAPI:
        def __init__(self):
            self.calls = []

        def write(self, **kwargs):
            self.calls.append(kwargs)

    monkeypatch.setattr("workers.predict.model_from_json", fake_model_from_json)
    monkeypatch.setattr(pipeline_worker, "MODELS_DIR", models_dir)
    monkeypatch.setattr(pipeline_worker, "STATIC_DIR", static_dir)
    monkeypatch.setattr(pipeline_worker, "PREDICTION_DISABLED_TIMEFRAMES", set())
    monkeypatch.setattr(pipeline_worker, "MIN_SAMPLE_BY_TIMEFRAME", {})
    monkeypatch.setattr(pipeline_worker, "INFLUXDB_BUCKET", "test_bucket")
    monkeypatch.setattr(pipeline_worker, "INFLUXDB_ORG", "test_org")

    write_api = FakeWriteAPI()
    result, error = predict_ops.run_prediction_and_save(
        pipeline_worker,
        write_api=write_api,
        query_api=None,
        symbol="BTC/USDT",
        timeframe="1h",
    )

    assert result == "ok"
    assert error is None
    assert loaded_payloads == ["canonical-json"]

    canonical_path = static_dir / "prediction_BTC_USDT_1h.json"
    assert canonical_path.exists()
    assert not (static_dir / "prediction_BTC_USDT.json").exists()

    payload = json.loads(canonical_path.read_text())
    assert payload["symbol"] == "BTC/USDT"
    assert payload["timeframe"] == "1h"
    assert isinstance(payload["forecast"], list)
    assert len(payload["forecast"]) == 24
    assert set(payload["forecast"][0].keys()) == {
        "timestamp",
        "price",
        "lower_bound",
        "upper_bound",
    }
    assert payload["forecast"][0]["timestamp"].endswith("Z")

    assert len(write_api.calls) == 1
    call = write_api.calls[0]
    assert call["bucket"] == "test_bucket"
    assert call["org"] == "test_org"

    record = call["record"]
    assert isinstance(record, pd.DataFrame)
    assert {"yhat", "yhat_lower", "yhat_upper", "symbol", "timeframe"}.issubset(
        record.columns
    )
    assert record.index.name == "timestamp"
    assert getattr(record.index, "tz", None) is not None
    assert set(record["symbol"].unique().tolist()) == {"BTC/USDT"}
    assert set(record["timeframe"].unique().tolist()) == {"1h"}


def test_predict_contract_fails_closed_when_only_legacy_model_exists(
    tmp_path, monkeypatch
):
    models_dir = tmp_path / "models"
    static_dir = tmp_path / "static_data"
    models_dir.mkdir(parents=True, exist_ok=True)

    legacy_model = models_dir / "model_BTC_USDT.json"
    legacy_model.write_text("legacy-json")

    loaded_payloads: list[str] = []

    def fake_model_from_json(raw: str):
        loaded_payloads.append(raw)
        return object()

    monkeypatch.setattr("workers.predict.model_from_json", fake_model_from_json)
    monkeypatch.setattr(pipeline_worker, "MODELS_DIR", models_dir)
    monkeypatch.setattr(pipeline_worker, "STATIC_DIR", static_dir)
    monkeypatch.setattr(pipeline_worker, "PREDICTION_DISABLED_TIMEFRAMES", set())
    monkeypatch.setattr(pipeline_worker, "MIN_SAMPLE_BY_TIMEFRAME", {})

    result, error = predict_ops.run_prediction_and_save(
        pipeline_worker,
        write_api=object(),
        query_api=None,
        symbol="BTC/USDT",
        timeframe="1h",
    )

    assert result == "failed"
    assert error == "model_missing"
    assert loaded_payloads == []
    assert not (static_dir / "prediction_BTC_USDT_1h.json").exists()
