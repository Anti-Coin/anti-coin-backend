from datetime import datetime, timezone

from admin.manifest_view import (
    MANIFEST_VIEW_COLUMNS,
    build_freshness_table,
    build_status_matrix,
    filter_manifest_entries,
    flatten_manifest_entries,
)


def _sample_manifest_payload() -> dict:
    return {
        "version": 1,
        "generated_at": "2026-02-19T08:00:00Z",
        "entries": [
            {
                "key": "BTC/USDT|1h",
                "symbol": "BTC/USDT",
                "timeframe": "1h",
                "history": {"updated_at": "2026-02-19T06:00:00Z"},
                "prediction": {
                    "status": "fresh",
                    "updated_at": "2026-02-19T07:00:00Z",
                    "age_minutes": 65.0,
                    "threshold_minutes": {"soft": 65, "hard": 130},
                },
                "degraded": False,
                "visibility": "visible",
                "symbol_state": "ready_for_serving",
                "last_prediction_success_at": "2026-02-19T07:00:00Z",
                "last_prediction_failure_at": None,
                "prediction_failure_count": 0,
                "serve_allowed": True,
            },
            {
                "key": "BTC/USDT|1d",
                "symbol": "BTC/USDT",
                "timeframe": "1d",
                "history": {"updated_at": "2026-02-18T00:00:00Z"},
                "prediction": {
                    "status": "stale",
                    "updated_at": "2026-02-17T00:00:00Z",
                    "age_minutes": 2880.0,
                    "threshold_minutes": {"soft": 1500, "hard": 3000},
                },
                "degraded": True,
                "visibility": "hidden_backfilling",
                "symbol_state": "backfilling",
                "last_prediction_success_at": "2026-02-17T00:00:00Z",
                "last_prediction_failure_at": "2026-02-18T00:00:00Z",
                "prediction_failure_count": 2,
                "serve_allowed": False,
            },
        ],
        "summary": {
            "entry_count": 2,
            "status_counts": {"fresh": 1, "stale": 1},
            "degraded_count": 1,
        },
    }


def test_flatten_manifest_entries_returns_expected_schema_and_delay():
    now = datetime(2026, 2, 19, 8, 0, tzinfo=timezone.utc)
    df = flatten_manifest_entries(_sample_manifest_payload(), now=now)

    assert list(df.columns) == MANIFEST_VIEW_COLUMNS
    assert len(df) == 2
    assert df.iloc[0]["timeframe"] == "1h"
    assert df.iloc[1]["timeframe"] == "1d"

    one_hour_row = df.loc[df["key"] == "BTC/USDT|1h"].iloc[0]
    assert one_hour_row["prediction_delay_minutes"] == 60.0
    assert one_hour_row["threshold_soft_minutes"] == 65
    assert one_hour_row["threshold_hard_minutes"] == 130


def test_build_status_matrix_marks_degraded_blocked_hidden():
    now = datetime(2026, 2, 19, 8, 0, tzinfo=timezone.utc)
    df = flatten_manifest_entries(_sample_manifest_payload(), now=now)

    matrix = build_status_matrix(df)

    assert matrix.loc["BTC/USDT", "1h"] == "FRESH"
    assert (
        matrix.loc["BTC/USDT", "1d"] == "STALE | DEG | BLOCK | HIDDEN"
    )


def test_filter_manifest_entries_applies_timeframe_status_and_modes():
    now = datetime(2026, 2, 19, 8, 0, tzinfo=timezone.utc)
    df = flatten_manifest_entries(_sample_manifest_payload(), now=now)

    filtered = filter_manifest_entries(
        df,
        symbols=["BTC/USDT"],
        timeframes=["1d"],
        statuses=["stale"],
        degraded_mode="only",
        serve_mode="exclude",
    )

    assert len(filtered) == 1
    assert filtered.iloc[0]["key"] == "BTC/USDT|1d"


def test_build_freshness_table_sorts_by_delay_desc():
    now = datetime(2026, 2, 19, 8, 0, tzinfo=timezone.utc)
    df = flatten_manifest_entries(_sample_manifest_payload(), now=now)

    table = build_freshness_table(df)

    assert table.iloc[0]["timeframe"] == "1d"
    assert table.iloc[0]["prediction_delay_minutes"] >= table.iloc[1][
        "prediction_delay_minutes"
    ]
