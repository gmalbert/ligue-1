"""Predictions tab — default home page for La Liga Linea."""

import json
import warnings
from datetime import datetime
from os import path

import numpy as np
import pandas as pd
import streamlit as st

from utils import (
    betting_recommendation,
    calculate_prediction_risk,
    color_risk_rows,
    generate_match_commentary,
    get_dataframe_height,
    render_table,
    risk_category,
)

warnings.filterwarnings("ignore")

PRED_LOG_PATH = "data_files/predictions_log.csv"
FIXTURES_PATH = "data_files/upcoming_fixtures.csv"
METRICS_PATH  = "models/metrics.json"

st.title("🎯 La Liga Predictions")
st.caption("Ensemble model: XGBoost · Random Forest · Gradient Boosting · Logistic Regression")

# ── Load pre-generated predictions ────────────────────────────────────────
if not path.exists(PRED_LOG_PATH):
    st.warning("Predictions are not yet available — they are generated nightly.")
    st.stop()

preds_log = pd.read_csv(PRED_LOG_PATH)

# Only show upcoming matches (no actual result recorded yet)
preds_log = preds_log[preds_log["ActualResult"].isna()].copy()

if preds_log.empty:
    st.info("No upcoming predictions available yet. Check back after the next nightly update.")
    st.stop()

# ── Model version selector ────────────────────────────────────────────────
available_models = sorted(preds_log["ModelVersion"].dropna().unique()) if "ModelVersion" in preds_log.columns else ["ensemble_v1"]
model_labels = {
    "ensemble_v1": "🤝 Ensemble (XGB + RF + GB + LR)",
    "nn_v1":       "🧠 Neural Network (LaLigaNet)",
}
if len(available_models) > 1:
    sel_model = st.selectbox(
        "Model",
        options=available_models,
        format_func=lambda x: model_labels.get(x, x),
        key="model_version_sel",
    )
    preds_log = preds_log[preds_log["ModelVersion"] == sel_model].copy()
else:
    sel_model = available_models[0] if available_models else "ensemble_v1"


# Attach kick-off times from the fixtures file
if path.exists(FIXTURES_PATH):
    fix_times = pd.read_csv(FIXTURES_PATH)[["HomeTeam", "AwayTeam", "Date", "Time"]]
    preds_log = preds_log.rename(columns={"MatchDate": "Date"})
    preds_log = preds_log.merge(fix_times, on=["HomeTeam", "AwayTeam", "Date"], how="left")
else:
    preds_log = preds_log.rename(columns={"MatchDate": "Date"})
    preds_log["Time"] = ""

# Convert stored percentages to raw probabilities for calculations
preds_log["_ph"] = preds_log["PredHomeWin"] / 100
preds_log["_pd"] = preds_log["PredDraw"]    / 100
preds_log["_pa"] = preds_log["PredAwayWin"] / 100

# Compute display columns (pure math — no model or API calls)
risk_rows = preds_log.apply(
    lambda r: pd.Series(
        calculate_prediction_risk(r["_ph"], r["_pd"], r["_pa"])
        + (risk_category(calculate_prediction_risk(r["_ph"], r["_pd"], r["_pa"])[0]),
           betting_recommendation(r["_ph"], r["_pd"], r["_pa"],
                                  calculate_prediction_risk(r["_ph"], r["_pd"], r["_pa"])[0])),
    ),
    axis=1,
)
risk_rows.columns = ["_rs", "_conf", "Risk Category", "Betting Tip"]

preds = preds_log.rename(columns={
    "PredHomeWin": "Home Win %",
    "PredDraw":    "Draw %",
    "PredAwayWin": "Away Win %",
}).copy()
preds["Risk Score"]   = risk_rows["_rs"].round(1)
preds["Risk Category"] = risk_rows["Risk Category"]
preds["Confidence %"] = (risk_rows["_conf"] * 100).round(1)
preds["Betting Tip"]  = risk_rows["Betting Tip"]

# ── Model info expander ────────────────────────────────────────────────────
metrics: dict = {}
if path.exists(METRICS_PATH):
    with open(METRICS_PATH) as f:
        metrics = json.load(f)

with st.expander("🤖 Model Info", expanded=False):
    if metrics:
        mc1, mc2, mc3, mc4 = st.columns(4)
        mc1.metric("Accuracy",   f"{metrics.get('accuracy', 0):.1%}")
        mc2.metric("F1 Macro",   f"{metrics.get('f1_macro', 0):.3f}")
        mc3.metric("Log Loss",   f"{metrics.get('log_loss', 0):.3f}")
        mc4.metric("Train Size", f"{metrics.get('n_train', 0):,}")
    st.caption("Predictions are pre-generated nightly via GitHub Actions.")

st.divider()

# ── Risk filter buttons ────────────────────────────────────────────────────
st.subheader("🎯 Upcoming Match Predictions")
last_updated = datetime.fromtimestamp(path.getmtime(PRED_LOG_PATH)).strftime("%b %d %H:%M") if path.exists(PRED_LOG_PATH) else "unknown"
st.caption(f"{len(preds)} fixtures · Predictions updated: {last_updated}")

fc1, fc2, fc3, fc4, fc5 = st.columns(5)
if "risk_filter" not in st.session_state:
    st.session_state["risk_filter"] = "All"

if fc1.button("📊 All",          width='stretch'): st.session_state["risk_filter"] = "All"
if fc2.button("🟢 Low",          width='stretch'): st.session_state["risk_filter"] = "Low"
if fc3.button("🟡 Moderate",     width='stretch'): st.session_state["risk_filter"] = "Moderate"
if fc4.button("🔴 High",         width='stretch'): st.session_state["risk_filter"] = "High"
if fc5.button("🚨 Critical",     width='stretch'): st.session_state["risk_filter"] = "Critical"

# ── Team filter ────────────────────────────────────────────────────────────
all_teams = sorted(set(preds["HomeTeam"].dropna()) | set(preds["AwayTeam"].dropna()))
selected_teams = st.multiselect(
    "Filter by team (leave blank for all):",
    options=all_teams,
    default=[],
    key="team_filter",
    placeholder="All teams",
)

# ── Date range filter ──────────────────────────────────────────────────────
preds["_dt"] = pd.to_datetime(preds["Date"], errors="coerce")
min_date = preds["_dt"].min().date() if preds["_dt"].notna().any() else None
max_date = preds["_dt"].max().date() if preds["_dt"].notna().any() else None

if min_date and max_date and min_date < max_date:
    dr_col1, dr_col2 = st.columns(2)
    with dr_col1:
        date_from = st.date_input("From date", value=min_date, min_value=min_date, max_value=max_date, key="date_from")
    with dr_col2:
        date_to   = st.date_input("To date",   value=max_date, min_value=min_date, max_value=max_date, key="date_to")
else:
    date_from = min_date
    date_to   = max_date

# Apply all filters
_filter = st.session_state.get("risk_filter", "All")
filtered = preds.copy()
if _filter != "All":
    filtered = filtered[filtered["Risk Category"].str.contains(_filter, na=False)]
if selected_teams:
    filtered = filtered[
        filtered["HomeTeam"].isin(selected_teams) | filtered["AwayTeam"].isin(selected_teams)
    ]
if date_from and date_to:
    filtered = filtered[
        (filtered["_dt"].dt.date >= date_from) & (filtered["_dt"].dt.date <= date_to)
    ]

if filtered.empty:
    st.info(f"No predictions with risk level: {_filter}")
    st.stop()

# ── Predictions table ──────────────────────────────────────────────────────
display_cols = [
    "Date", "Time", "HomeTeam", "AwayTeam",
    "Home Win %", "Draw %", "Away Win %",
    "Risk Score", "Risk Category", "Confidence %", "Betting Tip",
]
display_cols = [c for c in display_cols if c in filtered.columns]

styled = filtered[display_cols].style.apply(color_risk_rows, axis=1)
render_table(
    styled,
    hide_index=True,
    width='stretch',
    height=get_dataframe_height(filtered),
    column_config={
        "Home Win %": st.column_config.ProgressColumn(
            label="Home Win %", min_value=0, max_value=100, format="%.1f%%"
        ),
        "Draw %": st.column_config.ProgressColumn(
            label="Draw %",     min_value=0, max_value=100, format="%.1f%%"
        ),
        "Away Win %": st.column_config.ProgressColumn(
            label="Away Win %", min_value=0, max_value=100, format="%.1f%%"
        ),
    },
)

st.divider()

# ── Match commentary ───────────────────────────────────────────────────────
with st.expander("💬 Match Commentary", expanded=True):
    for _, row in filtered.iterrows():
        commentary = generate_match_commentary(
            row["HomeTeam"], row["AwayTeam"],
            row.get("_ph", 0.4), row.get("_pd", 0.27), row.get("_pa", 0.33),
            row.get("Risk Category", "🟡 Moderate"),
        )
        st.caption(f"**{row['HomeTeam']} vs {row['AwayTeam']}:** {commentary}")

st.divider()

# ── Download ───────────────────────────────────────────────────────────────
dl1, dl2 = st.columns([1, 3])
with dl1:
    csv_bytes = filtered[display_cols].to_csv(index=False).encode("utf-8")
    st.download_button(
        label="📥 Download CSV",
        data=csv_bytes,
        file_name=f"la_liga_predictions_{datetime.now().strftime('%Y%m%d')}.csv",
        mime="text/csv",
        width='stretch',
    )
