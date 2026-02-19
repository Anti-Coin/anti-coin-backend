import os
from datetime import datetime, timezone

import requests
import streamlit as st

from admin.manifest_view import (
    build_freshness_table,
    build_status_matrix,
    filter_manifest_entries,
    flatten_manifest_entries,
    status_cell_style,
    timeframe_sort_key,
)

st.set_page_config(page_title="Coin Predict MVP", layout="wide")

BASE_URL = os.getenv("API_URL", "http://nginx")
MANIFEST_URL = f"{BASE_URL}/static/manifest.json"


@st.cache_data(ttl=60)
def get_manifest_payload():
    """Manifest를 1차 소스로 조회한다."""
    try:
        response = requests.get(MANIFEST_URL, timeout=5)
        response.raise_for_status()
        payload = response.json()
        if not isinstance(payload, dict):
            raise ValueError("manifest payload is not a JSON object")
        return payload, None
    except Exception as e:
        return None, str(e)


st.title("Coin Predict Admin Dashboard")
st.markdown("Manifest-first runtime status board")

# 사이드바
st.sidebar.header("Control Panel")
if st.sidebar.button("Refresh Data"):
    st.cache_data.clear()

with st.spinner("Loading manifest from static user plane..."):
    manifest_payload, manifest_error = get_manifest_payload()

if manifest_error:
    st.error(f"Failed to fetch manifest: {manifest_error}")
    st.stop()
if manifest_payload is None:
    st.error("Manifest payload is empty.")
    st.stop()

summary = manifest_payload.get("summary", {})
entries_df = flatten_manifest_entries(
    manifest_payload, now=datetime.now(timezone.utc)
)

if entries_df.empty:
    st.warning("Manifest entries are empty. Wait for a publish cycle.")
    st.json({"summary": summary, "generated_at": manifest_payload.get("generated_at")})
    st.stop()

all_symbols = sorted(entries_df["symbol"].dropna().unique().tolist())
all_timeframes = sorted(
    entries_df["timeframe"].dropna().unique().tolist(),
    key=timeframe_sort_key,
)
all_statuses = sorted(entries_df["status"].dropna().unique().tolist())

selected_symbols = st.sidebar.multiselect(
    "Symbols",
    all_symbols,
    default=all_symbols,
)
selected_timeframes = st.sidebar.multiselect(
    "Timeframes",
    all_timeframes,
    default=all_timeframes,
)
selected_statuses = st.sidebar.multiselect(
    "Prediction Status",
    all_statuses,
    default=all_statuses,
)
degraded_mode = st.sidebar.selectbox(
    "Degraded Filter",
    ["all", "only", "exclude"],
    index=0,
)
serve_mode = st.sidebar.selectbox(
    "Serve Allowed Filter",
    ["all", "only", "exclude"],
    index=0,
)

filtered_df = filter_manifest_entries(
    entries_df,
    symbols=selected_symbols,
    timeframes=selected_timeframes,
    statuses=selected_statuses,
    degraded_mode=degraded_mode,
    serve_mode=serve_mode,
)

st.caption(
    f"Manifest generated_at={manifest_payload.get('generated_at')} / "
    f"entry_count={summary.get('entry_count', 0)}"
)

metric_col1, metric_col2, metric_col3, metric_col4 = st.columns(4)
metric_col1.metric(
    "Filtered Entries",
    len(filtered_df),
    f"of {summary.get('entry_count', 0)}",
)
metric_col2.metric(
    "Degraded",
    int(filtered_df["degraded"].sum()) if not filtered_df.empty else 0,
)
metric_col3.metric(
    "Blocked",
    int((~filtered_df["serve_allowed"]).sum()) if not filtered_df.empty else 0,
)
max_delay = (
    filtered_df["prediction_delay_minutes"].max()
    if not filtered_df.empty
    else None
)
metric_col4.metric(
    "Max Delay (min)",
    "-" if max_delay is None else f"{max_delay:.2f}",
)

st.subheader("Timeframe Status Matrix")
if filtered_df.empty:
    st.warning("No rows match current filters.")
else:
    matrix = build_status_matrix(filtered_df)
    st.dataframe(
        matrix.style.applymap(status_cell_style),
        use_container_width=True,
        height=320,
    )
    st.caption("Cell format: STATUS | DEG | BLOCK | HIDDEN")

st.subheader("Freshness and Updated-at Lag")
if filtered_df.empty:
    st.info("No freshness table for empty filter result.")
else:
    freshness_table = build_freshness_table(filtered_df).rename(
        columns={
            "prediction_updated_at": "prediction_updated_at_utc",
            "prediction_delay_minutes": "updated_delay_minutes",
            "prediction_age_minutes": "prediction_age_minutes_in_manifest",
            "history_updated_at": "history_updated_at_utc",
            "last_prediction_success_at": "last_success_at_utc",
            "last_prediction_failure_at": "last_failure_at_utc",
        }
    )
    st.dataframe(freshness_table, use_container_width=True, height=360)

st.subheader("Entry Detail")
if filtered_df.empty:
    st.info("No entry to inspect.")
else:
    selected_key = st.selectbox(
        "Select manifest entry",
        filtered_df["key"].tolist(),
    )
    selected_entry = (
        filtered_df.loc[filtered_df["key"] == selected_key]
        .iloc[0]
        .to_dict()
    )
    st.json(selected_entry)

with st.expander("View Raw Manifest JSON"):
    st.json(manifest_payload)
