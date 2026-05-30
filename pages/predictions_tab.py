"""Predictions tab — default home page for Ligue Odds."""

import json
import warnings
from datetime import datetime
from os import path
from pathlib import Path

import numpy as np
import pandas as pd
import streamlit as st

from utils import (
    betting_recommendation,
    calculate_prediction_risk,
    color_risk_rows,
    generate_match_commentary,
    get_dataframe_height,
    prediction_value_to_probability,
    render_table,
    risk_category,
)

warnings.filterwarnings("ignore")

PRED_LOG_PATH = "data_files/predictions_log.csv"
FIXTURES_PATH = "data_files/upcoming_fixtures.csv"
METRICS_PATH  = "models/metrics.json"
ODDS_PATH = "data_files/raw/odds.csv"
WEATHER_PATH = "data_files/raw/match_weather.csv"
APP_CACHE_DIR = Path("data_files/app_cache")
LOGO_PATH = Path("data_files/logo.png")


def _safe_read_csv(file_path: str | Path) -> pd.DataFrame:
    try:
        file_obj = Path(file_path)
        if not file_obj.exists():
            return pd.DataFrame()
        return pd.read_csv(file_obj)
    except Exception:
        return pd.DataFrame()


def _file_updated(file_path: str | Path) -> str:
    file_obj = Path(file_path)
    if not file_obj.exists():
        return "Missing"
    return datetime.fromtimestamp(file_obj.stat().st_mtime).strftime("%b %d %I:%M %p")


def _load_metrics() -> dict:
    if not path.exists(METRICS_PATH):
        return {}
    try:
        with open(METRICS_PATH) as f:
            return json.load(f)
    except Exception:
        return {}


def _render_empty_predictions_page(
    preds_log: pd.DataFrame,
    fixtures: pd.DataFrame,
    metrics: dict,
) -> None:
    st.subheader("Current Slate")

    status_cols = st.columns(4)
    status_cols[0].metric("Upcoming Fixtures", f"{len(fixtures):,}")
    status_cols[1].metric("Open Predictions", f"{len(preds_log):,}")
    status_cols[2].metric("Holdout Accuracy", f"{metrics.get('accuracy', 0):.1%}" if metrics else "Pending")
    status_cols[3].metric("Train Rows", f"{metrics.get('n_train', 0):,}" if metrics else "Pending")

    if fixtures.empty:
        st.info(
            "No scheduled Ligue 1 fixtures are available right now. "
            "The nightly job has cleared stale fixtures and predictions."
        )
    else:
        st.caption(f"Fixtures updated: {_file_updated(FIXTURES_PATH)}")
        fixture_cols = [c for c in ["Date", "Time", "Matchday", "HomeTeam", "AwayTeam", "Status"] if c in fixtures.columns]
        render_table(
            fixtures[fixture_cols].head(20),
            hide_index=True,
            width="stretch",
            height=get_dataframe_height(fixtures.head(20), max_height=420),
        )

    standings = _safe_read_csv(APP_CACHE_DIR / "standings.csv")
    if not standings.empty:
        st.divider()
        selected_season = st.session_state.get("selected_season", "2025-26")
        if "Season" in standings.columns:
            season_table = standings[standings["Season"] == selected_season].copy()
        else:
            season_table = pd.DataFrame()
        if season_table.empty:
            season_table = standings.tail(20).copy()
        season_table = season_table.drop(columns=["Season", "SeasonStart"], errors="ignore")
        if not season_table.empty:
            if "#" in season_table.columns:
                season_table["#"] = pd.to_numeric(season_table["#"], errors="coerce")
                season_table = season_table.sort_values("#", ascending=True)
            st.subheader("Standings")
            render_table(
                season_table.head(8),
                hide_index=True,
                width="stretch",
                height=get_dataframe_height(season_table.head(8), max_height=360),
            )

    st.divider()

    st.subheader("Explore")
    nav_cols = st.columns(4)
    nav_cols[0].page_link("pages/fixtures.py", label="Fixtures & Standings", icon="🗓️")
    nav_cols[1].page_link("pages/statistics.py", label="Statistics", icon="📊")
    nav_cols[2].page_link("pages/markets.py", label="Markets", icon="📈")
    nav_cols[3].page_link("pages/performance.py", label="Performance", icon="📈")

    feature_df = _safe_read_csv(APP_CACHE_DIR / "feature_importance.csv")
    if not feature_df.empty:
        st.divider()
        st.subheader("Top Model Signals")
        feature_df = feature_df.sort_values("Importance", ascending=False).head(6)
        render_table(feature_df, hide_index=True, width="stretch")

if LOGO_PATH.exists():
    st.image(str(LOGO_PATH), width=180)

st.title("🎯 Ligue 1 Predictions")
st.caption("Ensemble model: XGBoost · Random Forest · Gradient Boosting · Logistic Regression")

# ── Load pre-generated predictions ────────────────────────────────────────
metrics = _load_metrics()
fixtures = _safe_read_csv(FIXTURES_PATH)
preds_log = _safe_read_csv(PRED_LOG_PATH)

if preds_log.empty:
    _render_empty_predictions_page(preds_log, fixtures, metrics)
    st.stop()

# Only show upcoming matches (no actual result recorded yet)
if "ActualResult" in preds_log.columns:
    actual = preds_log["ActualResult"]
    preds_log = preds_log[actual.isna() | actual.astype(str).str.strip().eq("")].copy()

if preds_log.empty:
    _render_empty_predictions_page(preds_log, fixtures, metrics)
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

# Convert stored prediction values to raw probabilities for calculations.
preds_log["_ph"] = preds_log["PredHomeWin"].apply(prediction_value_to_probability)
preds_log["_pd"] = preds_log["PredDraw"].apply(prediction_value_to_probability)
preds_log["_pa"] = preds_log["PredAwayWin"].apply(prediction_value_to_probability)

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
preds["Home Win %"] = (preds_log["_ph"] * 100).round(1)
preds["Draw %"] = (preds_log["_pd"] * 100).round(1)
preds["Away Win %"] = (preds_log["_pa"] * 100).round(1)
preds["Risk Score"]   = risk_rows["_rs"].round(1)
preds["Risk Category"] = risk_rows["Risk Category"]
preds["Confidence %"] = (risk_rows["_conf"] * 100).round(1)
preds["Betting Tip"]  = risk_rows["Betting Tip"]

with st.expander("🤖 Model Info", expanded=False):
    if metrics:
        mc1, mc2, mc3, mc4 = st.columns(4)
        mc1.metric("Holdout Accuracy", f"{metrics.get('accuracy', 0):.1%}")
        mc2.metric("Market Baseline", f"{metrics.get('market_baseline_accuracy', 0):.1%}")
        mc3.metric("Log Loss Edge", f"{metrics.get('market_log_loss_delta', 0):+.3f}")
        mc4.metric("Draw Recall", f"{metrics.get('draw_recall', 0):.1%}")
        mc5, mc6, mc7, mc8 = st.columns(4)
        mc5.metric("Brier Score", f"{metrics.get('brier_score', 0):.3f}")
        mc6.metric("Calibration Error", f"{metrics.get('calibration_error', 0):.3f}")
        mc7.metric("ROI", f"{metrics.get('roi_pct', 0):+.1f}%")
        clv = metrics.get("closing_line_value_pct")
        mc8.metric("CLV", "N/A" if clv is None else f"{clv:+.2f}%")
        st.caption(
            f"Holdout season: {metrics.get('holdout_season', '?')} · "
            f"{metrics.get('test_start', '?')} to {metrics.get('test_end', '?')} · "
            f"Market blend weight: {metrics.get('market_blend_weight', 0):.2f} · "
            f"Train rows: {metrics.get('n_train', 0):,}"
        )
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
        file_name=f"ligue1_predictions_{datetime.now().strftime('%Y%m%d')}.csv",
        mime="text/csv",
        width='stretch',
    )
