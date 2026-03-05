"""
Prediction domain logic.

Why this module is separate:
- pipeline_worker는 orchestration에 집중하고, 예측 로직 변경은 여기서만 처리한다.
- 예측 실패/복구 정책(degraded 상태, last-good 유지)을 한 위치에서 일관되게 관리한다.
"""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

import pandas as pd
from prophet.serialize import model_from_json

from workers import ingest as ingest_ops
from utils.model_store import resolve_canonical_model_path
from utils.prediction_health_store import (
    load_prediction_health_entries,
    save_prediction_health_entries,
)


def load_prediction_health(ctx, path: Path) -> dict[str, dict]:
    """
    prediction health 파일 로드.

    Called from:
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
    entries, error_code = load_prediction_health_entries(path, logger=ctx.logger)
    if error_code in {"read_error", "format_error"}:
        return {}
    return entries


def save_prediction_health(ctx, entries: dict[str, dict], path: Path) -> None:
    """
    Prediction health 파일 저장.

    Called from:
      - `upsert_prediction_health`

    Why:
      - 상태 파일은 atomic write로 기록해 부분 쓰기 파일 노출을 방지한다.

    Args:
      - ctx: Context
      - entries: Prediction health 정보
      - path: Prediction health 파일 경로
    """
    save_prediction_health_entries(
        path,
        entries,
        atomic_write_json=ctx.atomic_write_json,
    )


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
    query_api,
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

    Orchestrator contract:
      - 이 함수는 watermark를 직접 갱신하지 않는다.
      - 반환 코드(ok/skipped/failed)를 바탕으로
        `scripts.pipeline_worker`가 predict watermark 전진 여부를 결정한다.
    """
    if not ctx.prediction_enabled_for_timeframe(timeframe):
        # 1m 등 비활성 timeframe은 "실패"가 아니라 정책적 skip으로 처리한다.
        # 그래야 알림/상태 체계가 정책 스킵을 장애로 오해하지 않는다.
        ctx.logger.info(
            f"[{symbol} {timeframe}] prediction disabled by policy. "
            "Skipping prediction artifact generation."
        )
        return "skipped", None

    # ── D-010: min sample gate ──
    min_sample = ctx.MIN_SAMPLE_BY_TIMEFRAME.get(timeframe)
    if min_sample is not None:
        sample_count = ingest_ops.count_ohlcv_rows(
            ctx,
            query_api,
            symbol=symbol,
            timeframe=timeframe,
        )
        if sample_count < min_sample:
            ctx.logger.info(
                f"[{symbol} {timeframe}] insufficient_data: "
                f"sample_count={sample_count}, min_required={min_sample}"
            )
            return "skipped", "insufficient_data"

    model_file = resolve_canonical_model_path(
        ctx.MODELS_DIR, symbol, timeframe
    )
    # D-040: legacy 단일 모델 fallback을 제거하고 canonical-only로 잠근다.
    # canonical 누락은 fail-closed(model_missing)로 처리한다.
    if not model_file.exists():
        ctx.logger.warning(
            f"[{symbol} {timeframe}] canonical model missing: {model_file}"
        )
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

        canonical_path = ctx._static_export_path("prediction", symbol, timeframe)
        ctx.atomic_write_json(canonical_path, json_output, indent=2)

        ctx.logger.info(
            f"[{symbol} {timeframe}] SSG 파일 생성 완료: "
            f"canonical={canonical_path} "
            f"(start={prediction_start.strftime('%Y-%m-%dT%H:%M:%SZ')}, "
            f"freq={timeframe})"
        )

        next_forecast["ds"] = pd.to_datetime(next_forecast["ds"]).dt.tz_localize("UTC")
        next_forecast = next_forecast[["ds", "yhat", "yhat_lower", "yhat_upper"]]
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
        ctx.logger.info(f"[{symbol} {timeframe}] {len(next_forecast)}개 예측 저장 완료")
        return "ok", None

    except Exception as e:
        ctx.logger.error(f"[{symbol} {timeframe}] 예측 에러: {e}")
        return "failed", f"prediction_error: {e}"
