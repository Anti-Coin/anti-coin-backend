import json
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path

from utils.config import (
    FRESHNESS_HARD_THRESHOLDS,
    FRESHNESS_THRESHOLDS,
    PRIMARY_TIMEFRAME,
)
from utils.freshness import classify_freshness, parse_utc_timestamp


@dataclass(frozen=True)
class PredictionStatusSnapshot:
    symbol: str
    timeframe: str
    status: str
    detail: str
    updated_at: str | None = None
    age_minutes: float | None = None
    soft_limit_minutes: int | None = None
    hard_limit_minutes: int | None = None
    error_code: str | None = None


def prediction_file_candidates(
    symbol: str, timeframe: str, static_dir: Path
) -> list[Path]:
    safe_symbol = symbol.replace("/", "_")
    timeframe_file = static_dir / f"prediction_{safe_symbol}_{timeframe}.json"
    legacy_file = static_dir / f"prediction_{safe_symbol}.json"

    # legacy fallback은 PRIMARY_TIMEFRAME에만 허용한다.
    # non-primary timeframe은 canonical 파일만 신뢰해 timeframe 오염을 막는다.
    if timeframe_file == legacy_file:
        return [legacy_file]
    if timeframe != PRIMARY_TIMEFRAME:
        return [timeframe_file]
    return [timeframe_file, legacy_file]


def _resolve_thresholds(
    timeframe: str,
    soft_thresholds: dict[str, timedelta] | None,
    hard_thresholds: dict[str, timedelta] | None,
) -> tuple[timedelta, timedelta]:
    resolved_soft = soft_thresholds or FRESHNESS_THRESHOLDS
    resolved_hard = hard_thresholds or FRESHNESS_HARD_THRESHOLDS

    default_soft = resolved_soft.get("1h", timedelta(minutes=65))
    default_hard = resolved_hard.get("1h", default_soft * 2)
    soft_limit = resolved_soft.get(timeframe, default_soft)
    hard_limit = resolved_hard.get(timeframe, max(default_hard, soft_limit * 2))
    return soft_limit, hard_limit


def evaluate_prediction_status(
    symbol: str,
    timeframe: str,
    now: datetime | None,
    static_dir: Path,
    soft_thresholds: dict[str, timedelta] | None = None,
    hard_thresholds: dict[str, timedelta] | None = None,
) -> PredictionStatusSnapshot:
    resolved_now = now or datetime.now(timezone.utc)
    soft_limit, hard_limit = _resolve_thresholds(
        timeframe, soft_thresholds, hard_thresholds
    )

    for file_path in prediction_file_candidates(symbol, timeframe, static_dir):
        if not file_path.exists():
            continue

        try:
            with open(file_path, "r") as f:
                payload = json.load(f)
        except json.JSONDecodeError:
            return PredictionStatusSnapshot(
                symbol=symbol,
                timeframe=timeframe,
                status="corrupt",
                detail=f"JSON decode error: {file_path.name}",
                error_code="json_decode_error",
            )
        except OSError as e:
            return PredictionStatusSnapshot(
                symbol=symbol,
                timeframe=timeframe,
                status="corrupt",
                detail=f"Read error: {file_path.name}: {e}",
                error_code="read_error",
            )

        updated_at_str = payload.get("updated_at")
        updated_at = parse_utc_timestamp(updated_at_str)
        if updated_at is None:
            return PredictionStatusSnapshot(
                symbol=symbol,
                timeframe=timeframe,
                status="corrupt",
                detail=f"Invalid updated_at format: {file_path.name}",
                error_code="invalid_updated_at",
            )

        freshness = classify_freshness(
            updated_at=updated_at,
            now=resolved_now,
            soft_limit=soft_limit,
            hard_limit=hard_limit,
        )
        return PredictionStatusSnapshot(
            symbol=symbol,
            timeframe=timeframe,
            status=freshness.status,
            detail=f"checked={file_path.name}",
            updated_at=updated_at.strftime("%Y-%m-%dT%H:%M:%SZ"),
            age_minutes=round(freshness.age.total_seconds() / 60, 2),
            soft_limit_minutes=int(freshness.soft_limit.total_seconds() // 60),
            hard_limit_minutes=int(freshness.hard_limit.total_seconds() // 60),
        )

    return PredictionStatusSnapshot(
        symbol=symbol,
        timeframe=timeframe,
        status="missing",
        detail="Prediction file is missing.",
        error_code="missing_file",
    )
