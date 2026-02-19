from __future__ import annotations

from datetime import datetime, timezone
from typing import Iterable

import pandas as pd

from utils.freshness import parse_utc_timestamp

MANIFEST_VIEW_COLUMNS = [
    "key",
    "symbol",
    "timeframe",
    "status",
    "degraded",
    "serve_allowed",
    "visibility",
    "symbol_state",
    "prediction_updated_at",
    "prediction_age_minutes",
    "prediction_delay_minutes",
    "threshold_soft_minutes",
    "threshold_hard_minutes",
    "history_updated_at",
    "last_prediction_success_at",
    "last_prediction_failure_at",
    "prediction_failure_count",
]


def timeframe_sort_key(timeframe: str) -> tuple[int, int, str]:
    if not isinstance(timeframe, str) or len(timeframe) < 2:
        return (99, 10**9, str(timeframe))

    amount_str = timeframe[:-1]
    unit = timeframe[-1]
    if not amount_str.isdigit():
        return (99, 10**9, timeframe)

    unit_order = {"m": 0, "h": 1, "d": 2, "w": 3, "M": 4}
    return (unit_order.get(unit, 99), int(amount_str), timeframe)


def _to_int(value) -> int | None:
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _to_float(value) -> float | None:
    try:
        return round(float(value), 2)
    except (TypeError, ValueError):
        return None


def _prediction_delay_minutes(
    prediction_updated_at: str | None, now: datetime
) -> float | None:
    if not prediction_updated_at:
        return None
    updated_at = parse_utc_timestamp(prediction_updated_at)
    if updated_at is None:
        return None
    delay = now - updated_at
    if delay.total_seconds() < 0:
        return 0.0
    return round(delay.total_seconds() / 60, 2)


def flatten_manifest_entries(
    manifest_payload: dict, now: datetime | None = None
) -> pd.DataFrame:
    resolved_now = now or datetime.now(timezone.utc)
    if resolved_now.tzinfo is None:
        resolved_now = resolved_now.replace(tzinfo=timezone.utc)
    else:
        resolved_now = resolved_now.astimezone(timezone.utc)

    entries = manifest_payload.get("entries")
    if not isinstance(entries, list):
        return pd.DataFrame(columns=MANIFEST_VIEW_COLUMNS)

    rows: list[dict] = []
    for entry in entries:
        if not isinstance(entry, dict):
            continue
        prediction = entry.get("prediction")
        if not isinstance(prediction, dict):
            prediction = {}
        history = entry.get("history")
        if not isinstance(history, dict):
            history = {}
        threshold_minutes = prediction.get("threshold_minutes")
        if not isinstance(threshold_minutes, dict):
            threshold_minutes = {}

        prediction_updated_at = prediction.get("updated_at")
        row = {
            "key": entry.get("key"),
            "symbol": entry.get("symbol"),
            "timeframe": entry.get("timeframe"),
            "status": prediction.get("status") or "unknown",
            "degraded": bool(entry.get("degraded", False)),
            "serve_allowed": bool(entry.get("serve_allowed", False)),
            "visibility": entry.get("visibility") or "unknown",
            "symbol_state": entry.get("symbol_state") or "unknown",
            "prediction_updated_at": prediction_updated_at,
            "prediction_age_minutes": _to_float(prediction.get("age_minutes")),
            "prediction_delay_minutes": _prediction_delay_minutes(
                prediction_updated_at, resolved_now
            ),
            "threshold_soft_minutes": _to_int(threshold_minutes.get("soft")),
            "threshold_hard_minutes": _to_int(threshold_minutes.get("hard")),
            "history_updated_at": history.get("updated_at"),
            "last_prediction_success_at": entry.get("last_prediction_success_at"),
            "last_prediction_failure_at": entry.get("last_prediction_failure_at"),
            "prediction_failure_count": _to_int(
                entry.get("prediction_failure_count")
            ),
        }
        rows.append(row)

    df = pd.DataFrame(rows, columns=MANIFEST_VIEW_COLUMNS)
    if df.empty:
        return df

    df["timeframe_sort_key"] = df["timeframe"].map(timeframe_sort_key)
    df.sort_values(
        by=["symbol", "timeframe_sort_key", "timeframe"],
        inplace=True,
        kind="stable",
    )
    df.drop(columns=["timeframe_sort_key"], inplace=True)
    df.reset_index(drop=True, inplace=True)
    return df


def _as_list(values: Iterable[str] | None) -> list[str]:
    if values is None:
        return []
    return [str(v) for v in values if str(v)]


def filter_manifest_entries(
    entries_df: pd.DataFrame,
    *,
    symbols: Iterable[str] | None = None,
    timeframes: Iterable[str] | None = None,
    statuses: Iterable[str] | None = None,
    degraded_mode: str = "all",
    serve_mode: str = "all",
) -> pd.DataFrame:
    if entries_df.empty:
        return entries_df.copy()

    mask = pd.Series(True, index=entries_df.index)

    selected_symbols = _as_list(symbols)
    if selected_symbols:
        mask &= entries_df["symbol"].isin(selected_symbols)

    selected_timeframes = _as_list(timeframes)
    if selected_timeframes:
        mask &= entries_df["timeframe"].isin(selected_timeframes)

    selected_statuses = _as_list(statuses)
    if selected_statuses:
        mask &= entries_df["status"].isin(selected_statuses)

    if degraded_mode == "only":
        mask &= entries_df["degraded"]
    elif degraded_mode == "exclude":
        mask &= ~entries_df["degraded"]

    if serve_mode == "only":
        mask &= entries_df["serve_allowed"]
    elif serve_mode == "exclude":
        mask &= ~entries_df["serve_allowed"]

    return entries_df.loc[mask].reset_index(drop=True)


def status_cell_label(row: pd.Series) -> str:
    parts = [str(row.get("status", "unknown")).upper()]
    if bool(row.get("degraded", False)):
        parts.append("DEG")
    if not bool(row.get("serve_allowed", False)):
        parts.append("BLOCK")
    if str(row.get("visibility", "visible")) == "hidden_backfilling":
        parts.append("HIDDEN")
    return " | ".join(parts)


def build_status_matrix(entries_df: pd.DataFrame) -> pd.DataFrame:
    if entries_df.empty:
        return pd.DataFrame()

    frame = entries_df.copy()
    frame["status_cell"] = frame.apply(status_cell_label, axis=1)

    matrix = frame.pivot_table(
        index="symbol",
        columns="timeframe",
        values="status_cell",
        aggfunc="first",
    )
    ordered_columns = sorted(matrix.columns.tolist(), key=timeframe_sort_key)
    return matrix.reindex(columns=ordered_columns)


def status_cell_style(cell_value) -> str:
    if not isinstance(cell_value, str):
        return ""

    normalized = cell_value.upper()
    if normalized.startswith("FRESH"):
        color = "#dcfce7"
    elif normalized.startswith("STALE"):
        color = "#fef3c7"
    elif normalized.startswith("HARD_STALE"):
        color = "#fee2e2"
    elif normalized.startswith("MISSING") or normalized.startswith("CORRUPT"):
        color = "#fecaca"
    else:
        color = "#e5e7eb"

    style = f"background-color: {color}; color: #111827;"
    if "BLOCK" in normalized:
        style += " font-weight: 700;"
    return style


def build_freshness_table(entries_df: pd.DataFrame) -> pd.DataFrame:
    if entries_df.empty:
        return pd.DataFrame()

    columns = [
        "symbol",
        "timeframe",
        "status",
        "degraded",
        "serve_allowed",
        "prediction_updated_at",
        "prediction_delay_minutes",
        "prediction_age_minutes",
        "history_updated_at",
        "prediction_failure_count",
        "last_prediction_success_at",
        "last_prediction_failure_at",
    ]
    table = entries_df[columns].copy()
    table.sort_values(
        by=["prediction_delay_minutes", "symbol", "timeframe"],
        ascending=[False, True, True],
        inplace=True,
        na_position="last",
        kind="stable",
    )
    table.reset_index(drop=True, inplace=True)
    return table
