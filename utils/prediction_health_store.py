"""
Prediction health state file helpers.

Why this module exists:
- API/worker가 동일 파일 계약(`prediction_health.json`)을 공유하므로
  파일 읽기/정규화 로직을 공통화해 drift를 줄인다.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable


def prediction_health_key(symbol: str, timeframe: str) -> str:
    return f"{symbol}|{timeframe}"


def load_prediction_health_entries(
    path: Path,
    *,
    logger=None,
) -> tuple[dict[str, dict], str | None]:
    """
    prediction_health 파일에서 entries를 읽는다.

    Returns:
    - (entries, None): 정상 로드
    - ({}, "missing"): 파일 없음
    - ({}, "read_error"): 파일 읽기/파싱 실패
    - ({}, "format_error"): entries 스키마 오류
    """
    if not path.exists():
        return {}, "missing"

    try:
        with open(path, "r") as f:
            payload = json.load(f)
    except (OSError, json.JSONDecodeError) as e:
        if logger is not None:
            logger.error(f"Prediction health read failed: {e}")
        return {}, "read_error"

    entries = payload.get("entries")
    if not isinstance(entries, dict):
        if logger is not None:
            logger.error("Prediction health format invalid: entries is not a dict.")
        return {}, "format_error"

    return entries, None


def build_prediction_health_status(
    path: Path,
    symbol: str,
    timeframe: str,
    *,
    logger=None,
) -> dict:
    """
    `/status` 응답용 prediction health 엔트리를 정규화해 반환한다.
    """
    default = {
        "degraded": False,
        "last_success_at": None,
        "last_failure_at": None,
        "last_error": None,
        "consecutive_failures": 0,
    }

    entries, error_code = load_prediction_health_entries(path, logger=logger)
    if error_code == "missing":
        return default

    if error_code in {"read_error", "format_error"}:
        degraded = default.copy()
        degraded["degraded"] = True
        degraded["last_error"] = (
            "prediction_health_read_error"
            if error_code == "read_error"
            else "prediction_health_format_error"
        )
        return degraded

    entry = entries.get(prediction_health_key(symbol, timeframe))
    if not isinstance(entry, dict):
        return default

    raw_failures = entry.get("consecutive_failures", 0)
    try:
        failures = int(raw_failures)
    except (TypeError, ValueError):
        failures = 0

    return {
        "degraded": bool(entry.get("degraded", False)),
        "last_success_at": entry.get("last_success_at"),
        "last_failure_at": entry.get("last_failure_at"),
        "last_error": entry.get("last_error"),
        "consecutive_failures": failures,
    }


def save_prediction_health_entries(
    path: Path,
    entries: dict[str, dict],
    *,
    atomic_write_json: Callable[..., None],
    now: datetime | None = None,
) -> None:
    """
    prediction_health entries를 파일 계약 형식으로 저장한다.
    """
    resolved_now = now or datetime.now(timezone.utc)
    payload = {
        "version": 1,
        "updated_at": resolved_now.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "entries": entries,
    }
    atomic_write_json(path, payload, indent=2)
