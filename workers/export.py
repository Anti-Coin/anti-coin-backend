"""
Export/manifest domain logic.

Why this module exists:
- 정적 산출물(history/prediction)과 manifest 생성 규칙을 한 곳에서 관리해
  사용자 데이터 플레인(SSG) 계약을 안정적으로 유지한다.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path


def static_export_candidates(
    ctx,
    kind: str,
    symbol: str,
    timeframe: str,
    static_dir: Path | None = None,
) -> list[Path]:
    """
    canonical/legacy 정적 파일 후보 경로를 우선순위 순으로 반환한다.

    Called from:
    - `extract_updated_at_from_files`
    - `build_runtime_manifest`

    Why:
    - 전환기 dual-write 환경에서 읽기 경로 단절 없이 최신 파일을 찾기 위함이다.
    """
    canonical, legacy = ctx._static_export_paths(
        kind, symbol, timeframe, static_dir=static_dir
    )
    candidates = [canonical]
    if legacy is not None:
        candidates.append(legacy)
    return candidates


def extract_updated_at_from_files(
    ctx,
    candidates: list[Path],
) -> tuple[str | None, str | None]:
    """
    후보 파일 중 첫 번째 유효한 `updated_at`과 source filename을 반환한다.

    Called from:
    - `build_runtime_manifest`

    Why:
    - manifest가 "어떤 파일에서 읽었는지"를 함께 남겨 디버깅 경로를 보존한다.
    """
    for path in candidates:
        if not path.exists():
            continue

        try:
            with open(path, "r") as f:
                payload = json.load(f)
        except (OSError, json.JSONDecodeError) as e:
            ctx.logger.error(
                f"Failed to read static export file {path.name}: {e}"
            )
            return None, path.name

        updated_at = payload.get("updated_at")
        if isinstance(updated_at, str) and updated_at:
            return updated_at, path.name

        ctx.logger.warning(
            f"Invalid updated_at in static export file: {path.name}"
        )
        return None, path.name

    return None, None


def build_runtime_manifest(
    ctx,
    symbols: list[str],
    timeframes: list[str],
    *,
    now: datetime | None = None,
    static_dir: Path | None = None,
    prediction_health_path: Path | None = None,
    symbol_activation_entries: dict[str, dict] | None = None,
) -> dict:
    """
    런타임 manifest payload를 생성한다.

    Called from:
    - `write_runtime_manifest`
    - tests(정적 상태 검증)

    Why:
    - 분산된 신호(history timestamp, prediction freshness, degraded, visibility)를
      단일 스냅샷으로 제공해 FE/운영 도구가 동일 기준으로 판단하도록 한다.

    Data-plane contract:
    - `serve_allowed`는 "노출 가능 여부 최종 비트"다.
    - visibility(hidden_backfilling) 또는 hard freshness 상태면 false가 된다.
    - FE는 세부 원인보다 이 비트를 1차 게이트로 사용하면 오노출을 줄일 수 있다.
    """
    resolved_now = now or datetime.now(timezone.utc)
    generated_at = resolved_now.strftime("%Y-%m-%dT%H:%M:%SZ")
    resolved_static_dir = static_dir or ctx.STATIC_DIR
    resolved_prediction_health_path = (
        prediction_health_path or ctx.PREDICTION_HEALTH_FILE
    )
    health_entries = ctx._load_prediction_health(
        path=resolved_prediction_health_path
    )

    entries: list[dict] = []
    status_counts: dict[str, int] = {}
    degraded_count = 0
    activation_entries = symbol_activation_entries or {}
    symbol_state_counts: dict[str, int] = {}
    visible_symbols: set[str] = set()

    for symbol in symbols:
        activation = activation_entries.get(symbol, {})
        visibility = (
            "visible"
            if activation.get("visibility") != "hidden_backfilling"
            else "hidden_backfilling"
        )
        symbol_state = activation.get("state", "ready_for_serving")
        is_full_backfilled = bool(
            activation.get("is_full_backfilled", visibility == "visible")
        )
        if visibility == "visible":
            visible_symbols.add(symbol)
        symbol_state_counts[symbol_state] = (
            symbol_state_counts.get(symbol_state, 0) + 1
        )

        for timeframe in timeframes:
            history_updated_at, history_file = extract_updated_at_from_files(
                ctx,
                static_export_candidates(
                    ctx,
                    "history",
                    symbol,
                    timeframe,
                    static_dir=resolved_static_dir,
                ),
            )
            snapshot = ctx.evaluate_prediction_status(
                symbol=symbol,
                timeframe=timeframe,
                now=resolved_now,
                static_dir=resolved_static_dir,
            )
            health = health_entries.get(
                ctx._prediction_health_key(symbol, timeframe), {}
            )
            degraded = bool(health.get("degraded", False))
            raw_failures = health.get("consecutive_failures", 0)
            try:
                failure_count = int(raw_failures)
            except (TypeError, ValueError):
                failure_count = 0
            if degraded:
                degraded_count += 1

            status_counts[snapshot.status] = (
                status_counts.get(snapshot.status, 0) + 1
            )
            entries.append(
                {
                    "key": ctx._prediction_health_key(symbol, timeframe),
                    "symbol": symbol,
                    "timeframe": timeframe,
                    "history": {
                        "updated_at": history_updated_at,
                        "source_file": history_file,
                    },
                    "prediction": {
                        "status": snapshot.status,
                        "updated_at": snapshot.updated_at,
                        "age_minutes": snapshot.age_minutes,
                        "threshold_minutes": {
                            "soft": snapshot.soft_limit_minutes,
                            "hard": snapshot.hard_limit_minutes,
                        },
                        "source_detail": snapshot.detail,
                    },
                    "degraded": degraded,
                    "last_prediction_success_at": health.get("last_success_at"),
                    "last_prediction_failure_at": health.get("last_failure_at"),
                    "prediction_failure_count": failure_count,
                    "visibility": visibility,
                    "symbol_state": symbol_state,
                    "is_full_backfilled": is_full_backfilled,
                    "coverage_start_at": activation.get("coverage_start_at"),
                    "coverage_end_at": activation.get("coverage_end_at"),
                    "exchange_earliest_at": activation.get(
                        "exchange_earliest_at"
                    ),
                    "serve_allowed": (
                        # serve_allowed는 fail-open 방지를 위해
                        # visibility + freshness 상태를 동시에 만족해야 한다.
                        visibility == "visible"
                        and snapshot.status in ctx.SERVE_ALLOWED_STATUSES
                    ),
                }
            )

    return {
        "version": 1,
        "generated_at": generated_at,
        "entries": entries,
        "summary": {
            "entry_count": len(entries),
            "status_counts": status_counts,
            "degraded_count": degraded_count,
            "visible_symbol_count": len(visible_symbols),
            "hidden_symbol_count": max(0, len(symbols) - len(visible_symbols)),
            "symbol_state_counts": symbol_state_counts,
        },
    }


def write_runtime_manifest(
    ctx,
    symbols: list[str],
    timeframes: list[str],
    *,
    now: datetime | None = None,
    static_dir: Path | None = None,
    prediction_health_path: Path | None = None,
    symbol_activation_entries: dict[str, dict] | None = None,
    path: Path | None = None,
) -> None:
    """
    manifest 생성 후 파일에 atomic write한다.

    Called from:
    - `scripts.pipeline_worker.run_worker` export stage 후반.

    Why:
    - 부분 쓰기 파일 노출을 피하고, 읽는 쪽(FE/admin)의 일관성을 유지한다.
    """
    resolved_path = path or ctx.MANIFEST_FILE
    payload = build_runtime_manifest(
        ctx,
        symbols,
        timeframes,
        now=now,
        static_dir=static_dir,
        prediction_health_path=prediction_health_path,
        symbol_activation_entries=symbol_activation_entries,
    )
    ctx.atomic_write_json(resolved_path, payload, indent=2)
    ctx.logger.info(f"Runtime manifest updated: {resolved_path}")


def save_history_to_json(ctx, df, symbol, timeframe):
    """
    history DataFrame을 정적 JSON으로 저장한다(canonical + legacy).

    Called from:
    - `update_full_history_file`

    Why:
    - 사용자 플레인이 SSG 기반이므로, export 시점마다 완결된 JSON 산출물이 필요하다.
    """
    try:
        export_df = df.copy()
        export_df["timestamp"] = export_df.index.strftime("%Y-%m-%dT%H:%M:%SZ")

        json_output = {
            "symbol": symbol,
            "data": export_df[
                ["timestamp", "open", "high", "low", "close", "volume"]
            ].to_dict(orient="records"),
            "updated_at": datetime.now(timezone.utc).strftime(
                "%Y-%m-%dT%H:%M:%SZ"
            ),
            "timeframe": timeframe,
            "type": f"history_{timeframe}",
        }

        canonical_path, legacy_path = ctx._static_export_paths(
            "history", symbol, timeframe
        )
        ctx.atomic_write_json(canonical_path, json_output)
        if legacy_path is not None:
            ctx.atomic_write_json(legacy_path, json_output)

        ctx.logger.info(
            f"[{symbol} {timeframe}] 정적 파일 생성 완료: "
            f"canonical={canonical_path}, legacy={legacy_path}"
        )
    except Exception as e:
        ctx.logger.error(f"[{symbol} {timeframe}] 정적 파일 생성 실패: {e}")


def update_full_history_file(ctx, query_api, symbol, timeframe) -> bool:
    """
    Influx source에서 history를 재조회해 정적 파일을 갱신한다.

    Called from:
    - `scripts.pipeline_worker.run_worker` publish/export stage.

    Why:
    - ingest 결과를 사용자 평면(정적 파일)으로 반영하는 공식 경로를 고정한다.
    """
    lookback_days = ctx._lookback_days_for_timeframe(timeframe)
    query = f"""
    from(bucket: "{ctx.INFLUXDB_BUCKET}")
      |> range(start: -{lookback_days}d)
      |> filter(fn: (r) => r["_measurement"] == "ohlcv")
      |> filter(fn: (r) => r["symbol"] == "{symbol}")
      |> filter(fn: (r) => r["timeframe"] == "{timeframe}")
      |> pivot(rowKey:["_time"], columnKey: ["_field"], valueColumn: "_value")
      |> sort(columns: ["_time"], desc: false)
    """
    try:
        df = query_api.query_data_frame(query)
        if df.empty:
            ctx.logger.warning(
                f"[{symbol} {timeframe}] history source query returned empty."
            )
            return False
        df.rename(columns={"_time": "timestamp"}, inplace=True)
        df.set_index("timestamp", inplace=True)
        save_history_to_json(ctx, df, symbol, timeframe)
        return True
    except Exception as e:
        ctx.logger.error(f"[{symbol} {timeframe}] History 갱신 중 에러: {e}")
        return False
