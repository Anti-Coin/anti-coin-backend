"""
Standalone model training entrypoint.

Why this file exists:
- 학습은 ingest/publish 운영 루프와 별도 실행되어야 한다.
- manual/one-shot 실행 경계를 명시해 운영 경로와 자원 경합을 통제한다.
"""

from __future__ import annotations

import argparse
import hashlib
import os
from pathlib import Path
from typing import Any

import pandas as pd
from prophet import Prophet
from influxdb_client import InfluxDBClient
from scripts.data_extractor import extract_ohlcv_to_parquet, _get_influx_client
from prophet.serialize import model_to_json

from utils.config import PRIMARY_TIMEFRAME, TARGET_SYMBOLS

BASE_DIR = Path(__file__).resolve().parent.parent
MODELS_DIR = BASE_DIR / "models"
STATIC_DIR = BASE_DIR / "static_data"
DEFAULT_LOOKBACK_LIMIT = 500
DEFAULT_MLFLOW_EXPERIMENT = "coin-train"


def _parse_csv(raw: str | None, *, default: list[str]) -> list[str]:
    if raw is None:
        return list(default)
    parsed = [value.strip() for value in raw.split(",") if value.strip()]
    return parsed if parsed else list(default)


def _require_positive_limit(limit: int) -> int:
    if limit <= 0:
        raise ValueError("TRAIN_LOOKBACK_LIMIT must be a positive integer.")
    return limit


def _parse_env_int(name: str, *, default: int) -> int:
    raw = os.getenv(name)
    if raw is None or not raw.strip():
        return default
    try:
        return int(raw)
    except ValueError:
        print(f"[Train] invalid env {name}={raw!r}. " f"Fallback to default={default}.")
        return default


def _resolve_model_paths(symbol: str, timeframe: str) -> tuple[Path, Path | None]:
    safe_symbol = symbol.replace("/", "_")
    canonical_path = MODELS_DIR / f"model_{safe_symbol}_{timeframe}.json"
    legacy_path: Path | None = None
    if timeframe == PRIMARY_TIMEFRAME:
        legacy_path = MODELS_DIR / f"model_{safe_symbol}.json"
    return canonical_path, legacy_path


def _resolve_mlflow_tracking_uri() -> str:
    raw = os.getenv("MLFLOW_TRACKING_URI")
    if raw and raw.strip():
        return raw.strip()
    return f"sqlite:///{STATIC_DIR / 'mlflow.db'}"


def _resolve_mlflow_experiment_name() -> str:
    raw = os.getenv("MLFLOW_EXPERIMENT_NAME")
    if raw and raw.strip():
        return raw.strip()
    return DEFAULT_MLFLOW_EXPERIMENT


def _load_mlflow_module() -> Any:
    try:
        import mlflow  # type: ignore
    except ModuleNotFoundError as exc:
        raise RuntimeError(
            "mlflow is required for training tracking. Install dependencies first."
        ) from exc
    return mlflow


def _resolve_training_plan(
    *,
    symbols_csv: str | None,
    timeframes_csv: str | None,
    lookback_limit: int,
) -> tuple[list[str], list[str], int]:
    symbols = _parse_csv(symbols_csv, default=TARGET_SYMBOLS)
    timeframes = _parse_csv(timeframes_csv, default=[PRIMARY_TIMEFRAME])
    return symbols, timeframes, _require_positive_limit(lookback_limit)


def _to_utc_text(value) -> str:
    ts = pd.Timestamp(value)
    if ts.tzinfo is None:
        ts = ts.tz_localize("UTC")
    else:
        ts = ts.tz_convert("UTC")
    return ts.strftime("%Y-%m-%dT%H:%M:%SZ")


def _prepare_prophet_train_df(df: pd.DataFrame) -> pd.DataFrame:
    """
    Prophet requires timezone-naive datetimes in `ds`.
    We normalize incoming timestamps to UTC and then drop timezone info.
    """
    train_df = df[["timestamp", "close"]].rename(
        columns={"timestamp": "ds", "close": "y"}
    )
    ds_utc = pd.to_datetime(train_df["ds"], utc=True, errors="raise")
    train_df["ds"] = ds_utc.dt.tz_convert("UTC").dt.tz_localize(None)
    return train_df


def train_and_save(
    symbol: str,
    timeframe: str,
    *,
    lookback_limit: int,
    client: InfluxDBClient,
    mlflow: Any,
) -> dict[str, Any]:
    print(f"[{symbol}] 모델 학습 시작...")
    run_name = f"{symbol.replace('/', '_')}__{timeframe}"

    with mlflow.start_run(run_name=run_name) as active_run:
        run_id = active_run.info.run_id
        # D-012 정책: snapshot은 latest 1개 경로로 유지한다.
        parquet_path = extract_ohlcv_to_parquet(
            symbol, timeframe, lookback_limit=lookback_limit, client=client
        )
        df = pd.read_parquet(parquet_path)
        row_count = int(len(df))

        mlflow.log_params(
            {
                "symbol": symbol,
                "timeframe": timeframe,
                "lookback_limit": lookback_limit,
                "snapshot_path": str(parquet_path),
            }
        )
        mlflow.log_metric("row_count", row_count)

        if df.empty:
            metadata = {
                "run_id": run_id,
                "symbol": symbol,
                "timeframe": timeframe,
                "row_count": 0,
                "data_range": {"start": None, "end": None},
                "model_version": None,
                "status": "skipped_insufficient_data",
            }
            mlflow.log_dict(metadata, "run_metadata.json")
            mlflow.set_tag("train_status", "skipped_insufficient_data")
            print(f"[{symbol}] 학습 데이터 부족. 건너뜁니다.")
            return metadata

        data_range = {
            "start": _to_utc_text(df["timestamp"].min()),
            "end": _to_utc_text(df["timestamp"].max()),
        }

        # Prophet 데이터 포맷 준비 (timezone-naive UTC `ds`)
        train_df = _prepare_prophet_train_df(df)

        # 학습
        model = Prophet(daily_seasonality=True)
        model.fit(train_df)

        # 저장 (canonical은 timeframe suffix 고정, primary는 legacy도 동시 기록)
        MODELS_DIR.mkdir(parents=True, exist_ok=True)
        canonical_path, legacy_path = _resolve_model_paths(symbol, timeframe)
        serialized_model = model_to_json(model)
        model_version = hashlib.sha256(serialized_model.encode("utf-8")).hexdigest()[
            :12
        ]
        with open(canonical_path, "w") as fout:
            fout.write(serialized_model)
        if legacy_path is not None:
            with open(legacy_path, "w") as fout:
                fout.write(serialized_model)

        metadata = {
            "run_id": run_id,
            "symbol": symbol,
            "timeframe": timeframe,
            "row_count": row_count,
            "data_range": data_range,
            "model_version": model_version,
            "status": "ok",
        }
        mlflow.log_param("model_version", model_version)
        mlflow.log_dict(metadata, "run_metadata.json")
        mlflow.log_artifact(str(canonical_path), artifact_path="models")
        if legacy_path is not None:
            mlflow.log_artifact(str(legacy_path), artifact_path="models")
        mlflow.set_tag("train_status", "ok")

        print(f"[{canonical_path}] 모델 저장 완료!")
        if legacy_path is not None:
            print(f"[{legacy_path}] legacy 모델 동기화 완료!")
        return metadata


def run_training_job(
    *,
    symbols: list[str],
    timeframes: list[str],
    lookback_limit: int,
) -> dict[str, Any]:
    mlflow = _load_mlflow_module()
    tracking_uri = _resolve_mlflow_tracking_uri()
    experiment_name = _resolve_mlflow_experiment_name()
    mlflow.set_tracking_uri(tracking_uri)
    mlflow.set_experiment(experiment_name)
    print(
        "[Train] tracking backend uri=%s experiment=%s"
        % (tracking_uri, experiment_name)
    )

    results: list[dict[str, Any]] = []
    failures: list[dict[str, Any]] = []

    client = _get_influx_client()
    try:
        for symbol in symbols:
            for timeframe in timeframes:
                try:
                    result = train_and_save(
                        symbol,
                        timeframe,
                        lookback_limit=lookback_limit,
                        client=client,
                        mlflow=mlflow,
                    )
                    results.append(result)
                except Exception as exc:
                    failures.append(
                        {
                            "symbol": symbol,
                            "timeframe": timeframe,
                            "error": str(exc),
                        }
                    )
                    print(
                        "[Train] failed symbol=%s timeframe=%s error=%s"
                        % (symbol, timeframe, exc)
                    )
    finally:
        client.close()

    summary = {
        "total": len(symbols) * len(timeframes),
        "succeeded": len([r for r in results if r.get("status") == "ok"]),
        "skipped": len(
            [r for r in results if r.get("status") == "skipped_insufficient_data"]
        ),
        "failed": len(failures),
        "failures": failures,
    }
    print(
        "[Train] summary total=%s succeeded=%s skipped=%s failed=%s"
        % (
            summary["total"],
            summary["succeeded"],
            summary["skipped"],
            summary["failed"],
        )
    )
    return summary


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Run standalone one-shot model training without ingest/publish loop."
        )
    )
    parser.add_argument(
        "--symbols",
        default=os.getenv("TRAIN_SYMBOLS"),
        help=(
            "Comma-separated symbols. Default: TRAIN_SYMBOLS "
            "or TARGET_SYMBOLS from config."
        ),
    )
    parser.add_argument(
        "--timeframes",
        default=os.getenv("TRAIN_TIMEFRAMES"),
        help=(
            "Comma-separated timeframes. Default: TRAIN_TIMEFRAMES "
            f"or {PRIMARY_TIMEFRAME}."
        ),
    )
    parser.add_argument(
        "--lookback-limit",
        type=int,
        default=_parse_env_int("TRAIN_LOOKBACK_LIMIT", default=DEFAULT_LOOKBACK_LIMIT),
        help=f"OHLCV candle lookback size (default: {DEFAULT_LOOKBACK_LIMIT}).",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_arg_parser().parse_args(argv)

    try:
        symbols, timeframes, lookback_limit = _resolve_training_plan(
            symbols_csv=args.symbols,
            timeframes_csv=args.timeframes,
            lookback_limit=args.lookback_limit,
        )
    except ValueError as exc:
        print(f"[Train] invalid argument: {exc}")
        return 2

    print(
        "[Train] start symbols=%s timeframes=%s lookback_limit=%s"
        % (symbols, timeframes, lookback_limit)
    )
    summary = run_training_job(
        symbols=symbols, timeframes=timeframes, lookback_limit=lookback_limit
    )
    if summary["failed"] > 0:
        print("[Train] completed_with_partial_failures")
        return 1
    print("[Train] completed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
