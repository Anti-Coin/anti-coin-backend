"""
Prediction domain logic.

Why this module is separate:
- pipeline_worker는 orchestration에 집중하고, 예측 로직 변경은 여기서만 처리한다.
- 예측 실패/복구 정책(degraded 상태, last-good 유지)을 한 위치에서 일관되게 관리한다.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd
from prophet.serialize import model_from_json


def load_prediction_health(ctx, path: Path) -> dict[str, dict]:
    """
    prediction health 파일 로드.

    Called from:
      - `scripts.pipeline_worker._load_prediction_health`
      - `upsert_prediction_health`

    Why:
      - degraded/recovery 상태는 파일 기반으로 보존되어야 worker 재시작 시에도
        경보 의미가 유지된다.

    Args:
      - ctx: Context
      - path: Prediction health 파일 경로
    Returns:
      - dict[str, dict]: Prediction health 정보
    """
    if not path.exists():
        return {}

    try:
        with open(path, "r") as f:
            payload = json.load(f)
    except (OSError, json.JSONDecodeError) as e:
        ctx.logger.error(f"Failed to load prediction health file: {e}")
        return {}

    entries = payload.get("entries")
    if not isinstance(entries, dict):
        ctx.logger.error(
            "Invalid prediction health format: entries is not a dict."
        )
        return {}
    return entries


def save_prediction_health(ctx, entries: dict[str, dict], path: Path) -> None:
    """
    Prediction health 파일 저장.

    Called from:
      - `scripts.pipeline_worker._save_prediction_health`
      - `upsert_prediction_health`

    Why:
      - 상태 파일은 atomic write로 기록해 부분 쓰기 파일 노출을 방지한다.

    Args:
      - ctx: Context
      - entries: Prediction health 정보
      - path: Prediction health 파일 경로
    """
    payload = {
        "version": 1,
        "updated_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "entries": entries,
    }
    ctx.atomic_write_json(path, payload, indent=2)


def upsert_prediction_health(
    ctx,
    symbol: str,
    timeframe: str,
    *,
    prediction_ok: bool,
    error: str | None = None,
    path: Path,
) -> tuple[dict, bool, bool]:
    """
    prediction 성공/실패 결과를 health state에 반영한다.

    Called from:
      - `scripts.pipeline_worker.upsert_prediction_health`

    Why:
      - 단순 최근 실패 여부만으로는 운영 신호가 약하므로,
        degraded 전이와 연속 실패 횟수를 함께 기록한다.
    """
    entries = load_prediction_health(ctx, path=path)
    key = ctx._prediction_health_key(symbol, timeframe)
    now_utc = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    previous = entries.get(key, {})
    was_degraded = bool(previous.get("degraded", False))

    if prediction_ok:
        updated = {
            "symbol": symbol,
            "timeframe": timeframe,
            "degraded": False,
            "last_success_at": now_utc,
            "last_failure_at": previous.get("last_failure_at"),
            "consecutive_failures": 0,
            "last_error": None,
            "updated_at": now_utc,
        }
    else:
        previous_failures = previous.get("consecutive_failures", 0)
        try:
            previous_failures_int = int(previous_failures)
        except (TypeError, ValueError):
            previous_failures_int = 0
        updated = {
            "symbol": symbol,
            "timeframe": timeframe,
            "degraded": True,
            "last_success_at": previous.get("last_success_at"),
            "last_failure_at": now_utc,
            "consecutive_failures": max(0, previous_failures_int) + 1,
            "last_error": error or "prediction_failed",
            "updated_at": now_utc,
        }

    entries[key] = updated
    save_prediction_health(ctx, entries, path=path)

    return updated, was_degraded, bool(updated["degraded"])


def run_prediction_and_save(
    ctx,
    write_api,
    symbol,
    timeframe,
) -> tuple[str, str | None]:
    """
    모델 로드 -> 예측 생성 -> 정적 파일/Influx 저장을 수행한다.

    Called from:
      - `scripts.pipeline_worker.run_prediction_and_save`
      - 최종적으로 `scripts.pipeline_worker.run_worker` publish/predict 단계

    Why:
      - publish 단계가 ingest 결과를 사용자/운영 산출물로 반영하는 핵심 경로이므로
        정책 스킵/실패/성공 상태를 명확한 return code로 분리한다.
    """
    if not ctx.prediction_enabled_for_timeframe(timeframe):
        # 1m 등 비활성 timeframe은 "실패"가 아니라 정책적 skip으로 처리한다.
        # 그래야 알림/상태 체계가 정책 스킵을 장애로 오해하지 않는다.
        ctx.logger.info(
            f"[{symbol} {timeframe}] prediction disabled by policy. "
            "Skipping prediction artifact generation."
        )
        return "skipped", None

    safe_symbol = symbol.replace("/", "_")
    model_candidates = [
        ctx.MODELS_DIR / f"model_{safe_symbol}_{timeframe}.json",
        ctx.MODELS_DIR / f"model_{safe_symbol}.json",
    ]
    # timeframe 전용 모델 우선, 없으면 legacy 단일 모델 fallback.
    # 이 순서를 유지하면 다중 timeframe 전환 중에도 서비스 중단 없이 점진 전환 가능하다.
    model_file = next(
        (candidate for candidate in model_candidates if candidate.exists()),
        None,
    )
    if model_file is None:
        ctx.logger.warning(f"[{symbol} {timeframe}] 모델 없음")
        return "failed", "model_missing"

    try:
        with open(model_file, "r") as fin:
            model = model_from_json(fin.read())

        now = datetime.now(timezone.utc)
        # 예측 시작점은 "현재 시각"이 아니라 "다음 닫힌 캔들 경계"다.
        # 이유: 미완료 구간(open candle) 예측을 피하고, 백테스트/운영 시계열 축을
        # 안정적으로 맞추기 위해서다.
        prediction_start = ctx.next_timeframe_boundary(now, timeframe)
        prediction_freq = ctx.timeframe_to_pandas_freq(timeframe)
        future = pd.DataFrame(
            {
                "ds": pd.date_range(
                    start=prediction_start, periods=24, freq=prediction_freq
                )
            }
        )
        future["ds"] = future["ds"].dt.tz_localize(None)

        forecast = model.predict(future)
        next_forecast = forecast.head(24).copy()

        if next_forecast.empty:
            ctx.logger.warning(f"[{symbol} {timeframe}] 예측 범위 생성 실패.")
            return "failed", "empty_forecast"

        export_data = next_forecast[["ds", "yhat", "yhat_lower", "yhat_upper"]]
        export_data["ds"] = pd.to_datetime(export_data["ds"]).dt.strftime(
            "%Y-%m-%dT%H:%M:%SZ"
        )
        export_data.rename(
            columns={
                "ds": "timestamp",
                "yhat": "price",
                "yhat_lower": "lower_bound",
                "yhat_upper": "upper_bound",
            },
            inplace=True,
        )

        json_output = {
            "symbol": symbol,
            "timeframe": timeframe,
            "updated_at": now.strftime("%Y-%m-%dT%H:%M:%SZ"),
            "forecast": export_data.to_dict(orient="records"),
        }

        canonical_path, legacy_path = ctx._static_export_paths(
            "prediction", symbol, timeframe
        )
        # canonical + legacy dual-write는 이행기 호환 장치다.
        # 하위 소비자가 canonical로 완전 전환되기 전까지 읽기 경로 단절을 막는다.
        ctx.atomic_write_json(canonical_path, json_output, indent=2)
        if legacy_path is not None:
            ctx.atomic_write_json(legacy_path, json_output, indent=2)

        ctx.logger.info(
            f"[{symbol} {timeframe}] SSG 파일 생성 완료: "
            f"canonical={canonical_path}, legacy={legacy_path} "
            f"(start={prediction_start.strftime('%Y-%m-%dT%H:%M:%SZ')}, "
            f"freq={timeframe})"
        )

        next_forecast["ds"] = pd.to_datetime(
            next_forecast["ds"]
        ).dt.tz_localize("UTC")
        next_forecast = next_forecast[
            ["ds", "yhat", "yhat_lower", "yhat_upper"]
        ]
        next_forecast.rename(columns={"ds": "timestamp"}, inplace=True)
        next_forecast.set_index("timestamp", inplace=True)
        next_forecast["symbol"] = symbol
        next_forecast["timeframe"] = timeframe

        write_api.write(
            bucket=ctx.INFLUXDB_BUCKET,
            org=ctx.INFLUXDB_ORG,
            record=next_forecast,
            data_frame_measurement_name="prediction",
            data_frame_tag_columns=["symbol", "timeframe"],
        )
        # 정적 JSON 외에 Influx에도 prediction을 남기는 이유:
        # - 운영 분석(추세/실패 구간)과 추후 모델 비교(shadow/champion)의
        #   기준 데이터를 보존하기 위해서다.
        ctx.logger.info(
            f"[{symbol} {timeframe}] {len(next_forecast)}개 예측 저장 완료"
        )
        return "ok", None

    except Exception as e:
        ctx.logger.error(f"[{symbol} {timeframe}] 예측 에러: {e}")
        return "failed", f"prediction_error: {e}"
