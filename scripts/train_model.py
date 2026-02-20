"""
Standalone model training entrypoint.

Why this file exists:
- 학습은 ingest/publish 운영 루프와 별도 실행되어야 한다.
- manual/one-shot 실행 경계를 명시해 운영 경로와 자원 경합을 통제한다.
"""

from __future__ import annotations

import argparse
import os
from pathlib import Path

import ccxt
import pandas as pd
from prophet import Prophet
from prophet.serialize import model_to_json

from utils.config import PRIMARY_TIMEFRAME, TARGET_SYMBOLS

BASE_DIR = Path(__file__).resolve().parent.parent
MODELS_DIR = BASE_DIR / "models"
DEFAULT_LOOKBACK_LIMIT = 500


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
        print(
            f"[Train] invalid env {name}={raw!r}. "
            f"Fallback to default={default}."
        )
        return default


def _resolve_model_paths(symbol: str, timeframe: str) -> tuple[Path, Path | None]:
    safe_symbol = symbol.replace("/", "_")
    canonical_path = MODELS_DIR / f"model_{safe_symbol}_{timeframe}.json"
    legacy_path: Path | None = None
    if timeframe == PRIMARY_TIMEFRAME:
        legacy_path = MODELS_DIR / f"model_{safe_symbol}.json"
    return canonical_path, legacy_path


def _resolve_training_plan(
    *,
    symbols_csv: str | None,
    timeframes_csv: str | None,
    lookback_limit: int,
) -> tuple[list[str], list[str], int]:
    symbols = _parse_csv(symbols_csv, default=TARGET_SYMBOLS)
    timeframes = _parse_csv(timeframes_csv, default=[PRIMARY_TIMEFRAME])
    return symbols, timeframes, _require_positive_limit(lookback_limit)


def train_and_save(
    symbol: str,
    timeframe: str,
    *,
    lookback_limit: int,
    exchange: ccxt.Exchange,
):
    print(f"[{symbol}] 모델 학습 시작...")

    # 데이터 수집 (최근 lookback_limit candle)
    ohlcv = exchange.fetch_ohlcv(symbol, timeframe, limit=lookback_limit)
    df = pd.DataFrame(
        ohlcv, columns=["timestamp", "open", "high", "low", "close", "volume"]
    )
    df["timestamp"] = pd.to_datetime(df["timestamp"], unit="ms")

    # Prophet 데이터 포맷 준비
    train_df = df[["timestamp", "close"]].rename(
        columns={"timestamp": "ds", "close": "y"}
    )

    # 학습
    model = Prophet(daily_seasonality=True)
    model.fit(train_df)

    # 저장 (canonical은 timeframe suffix 고정, primary는 legacy도 동시 기록)
    MODELS_DIR.mkdir(parents=True, exist_ok=True)
    canonical_path, legacy_path = _resolve_model_paths(symbol, timeframe)
    serialized_model = model_to_json(model)
    with open(canonical_path, "w") as fout:
        fout.write(serialized_model)
    if legacy_path is not None:
        with open(legacy_path, "w") as fout:
            fout.write(serialized_model)

    print(f"[{canonical_path}] 모델 저장 완료!")
    if legacy_path is not None:
        print(f"[{legacy_path}] legacy 모델 동기화 완료!")


def run_training_job(
    *,
    symbols: list[str],
    timeframes: list[str],
    lookback_limit: int,
) -> None:
    exchange = ccxt.binance()
    for symbol in symbols:
        for timeframe in timeframes:
            train_and_save(
                symbol,
                timeframe,
                lookback_limit=lookback_limit,
                exchange=exchange,
            )


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
        default=_parse_env_int(
            "TRAIN_LOOKBACK_LIMIT", default=DEFAULT_LOOKBACK_LIMIT
        ),
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
    run_training_job(
        symbols=symbols, timeframes=timeframes, lookback_limit=lookback_limit
    )
    print("[Train] completed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
