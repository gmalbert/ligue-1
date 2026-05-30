"""Prediction Performance page — rolling accuracy and ROI tracker."""

from __future__ import annotations

import json
from os import path

import pandas as pd
import plotly.express as px
import streamlit as st

from utils import prediction_value_to_probability, render_table
from themes import plotly_theme

LOG_PATH      = "data_files/predictions_log.csv"
BACKTEST_PATH = "models/backtest_results.json"
METRICS_PATH  = "models/metrics.json"

st.title("📈 Prediction Performance")

# ── Model Metrics Banner ──────────────────────────────────────────────────
if path.exists(METRICS_PATH):
    with open(METRICS_PATH) as f:
        m = json.load(f)
    mc1, mc2, mc3, mc4 = st.columns(4)
    mc1.metric("Holdout Accuracy", f"{m.get('accuracy', 0):.1%}")
    mc2.metric("Market Baseline", f"{m.get('market_baseline_accuracy', 0):.1%}")
    mc3.metric("Log Loss Edge", f"{m.get('market_log_loss_delta', 0):+.3f}")
    mc4.metric("Brier Score", f"{m.get('brier_score', 0):.3f}")
    mc5, mc6, mc7, mc8 = st.columns(4)
    mc5.metric("Calibration Error", f"{m.get('calibration_error', 0):.3f}")
    mc6.metric("Draw Recall", f"{m.get('draw_recall', 0):.1%}")
    mc7.metric("ROI", f"{m.get('roi_pct', 0):+.1f}%")
    clv = m.get("closing_line_value_pct")
    mc8.metric("CLV", "N/A" if clv is None else f"{clv:+.2f}%")
    st.caption(
        f"Holdout season: {m.get('holdout_season', '?')} · "
        f"{m.get('test_start', '?')} to {m.get('test_end', '?')} · "
        f"Market blend weight: {m.get('market_blend_weight', 0):.2f} · "
        f"Macro F1: {m.get('f1_macro', 0):.3f} · ROC AUC: {m.get('roc_auc_ovr_macro', 0) or 0:.3f}"
    )

st.divider()

# ── Predictions Log ────────────────────────────────────────────────────────
if not path.exists(LOG_PATH):
    st.info("No predictions log found — predictions are pre-generated nightly via GitHub Actions.")
    st.stop()

log = pd.read_csv(LOG_PATH)

# Normalise columns
log["MatchDate"] = pd.to_datetime(log["MatchDate"], errors="coerce")
if "Correct" in log.columns:
    log["Correct"] = pd.to_numeric(log["Correct"], errors="coerce")
for pred_col in ["PredHomeWin", "PredDraw", "PredAwayWin"]:
    if pred_col in log.columns:
        log[pred_col] = log[pred_col].apply(prediction_value_to_probability)

# Focus only on resolved (ActualResult known)
resolved = log[log["ActualResult"].notna() & (log["ActualResult"] != "")].copy()

if resolved.empty:
    st.info(
        "No resolved predictions yet — **Actual Results** are populated after each match day. "
        "Check back once matches have been played."
    )
else:
    total    = len(resolved)
    correct  = int(resolved["Correct"].sum()) if "Correct" in resolved.columns else 0
    accuracy = correct / total if total > 0 else 0.0

    pc1, pc2, pc3 = st.columns(3)
    pc1.metric("Resolved Predictions", total)
    pc2.metric("Correct",              correct)
    pc3.metric("Live Accuracy",        f"{accuracy:.1%}")

    st.divider()

    # Rolling accuracy chart
    if "MatchDate" in resolved.columns and "Correct" in resolved.columns:
        res_sorted = resolved.sort_values("MatchDate").copy()
        res_sorted["CumAccuracy"] = (
            res_sorted["Correct"].expanding().mean() * 100
        )

        fig = px.line(
            res_sorted,
            x="MatchDate",
            y="CumAccuracy",
            title="Cumulative Prediction Accuracy Over Time",
            labels={"MatchDate": "Match Date", "CumAccuracy": "Accuracy (%)"},
        )
        fig.add_hline(y=33.3, line_dash="dash", line_color="gray",
                      annotation_text="Random baseline (33.3%)")
        fig.update_traces(line_color="#e63946", line_width=2)
        fig.update_layout(yaxis_range=[0, 100], hovermode="x unified",
                          **plotly_theme())
        st.plotly_chart(fig, width='stretch')

    st.divider()

    # Results breakdown
    st.subheader("📋 Prediction Log (Resolved)")
    show_cols = [c for c in
                 ["MatchDate", "HomeTeam", "AwayTeam", "PredictedResult",
                  "ActualResult", "Correct", "PredHomeWin", "PredDraw", "PredAwayWin"]
                 if c in resolved.columns]

    def _row_style(row: pd.Series) -> list[str]:
        import streamlit as st
        dark = st.session_state.get("dark_mode", True)
        if row.get("Correct") == 1:
            s = "background-color: rgba(46,204,113,0.15)" if dark else "background-color: #d4edda; color: #0a3a1a"
        elif row.get("Correct") == 0:
            s = "background-color: rgba(231,76,60,0.15)" if dark else "background-color: #cce5ff; color: #0a1e3a"
        else:
            s = "" if dark else "background-color: #f0f8ff; color: #0a1428"
        return [s] * len(row)

    styled = (
        resolved[show_cols]
        .sort_values("MatchDate", ascending=False)
        .style.apply(_row_style, axis=1)
        .format({
            "PredHomeWin": "{:.1%}",
            "PredDraw":    "{:.1%}",
            "PredAwayWin": "{:.1%}",
        }, na_rep="—")
    )
    render_table(styled, hide_index=True, width='stretch')

st.divider()

# ── Backtesting Results (Historical) ──────────────────────────────────────
st.subheader("🧪 Historical Backtest (Ensemble vs Bet365)")

if path.exists(BACKTEST_PATH):
    with open(BACKTEST_PATH) as f:
        bt = json.load(f)

    bc1, bc2, bc3, bc4 = st.columns(4)
    bc1.metric("Backtest Accuracy",  f"{bt.get('accuracy', 0):.1%}")
    bc2.metric("Market Accuracy",    f"{bt.get('market_accuracy', 0):.1%}")
    bc3.metric("Bets Placed",        bt.get("n_bets_placed", 0))
    bc4.metric("Flat-Stake ROI",     f"{bt.get('roi_pct', 0):+.1f}%")
    bc5, bc6, bc7, bc8 = st.columns(4)
    bc5.metric("Log Loss Edge", f"{bt.get('market_log_loss_delta', 0):+.3f}")
    bc6.metric("Calibration Error", f"{bt.get('calibration_error', 0):.3f}")
    bc7.metric("Draw Recall", f"{bt.get('draw_recall', 0):.1%}")
    clv = bt.get("closing_line_value_pct")
    bc8.metric("CLV", "N/A" if clv is None else f"{clv:+.2f}%")
    st.caption(
        f"Holdout season: {bt.get('holdout_season', '?')} · "
        f"Brier score: {bt.get('brier_score', 0):.4f} · "
        f"Market Brier: {bt.get('market_brier_score', 0):.4f}"
    )

    with st.expander("ℹ️ How the backtest works"):
        st.markdown(
            """
            **Methodology:**
            - The ensemble model is evaluated on the latest full season holdout, not rows used for training.
            - Accuracy is exact 3-way classification accuracy: home win, draw, or away win.
            - Log Loss Edge is market log loss minus model log loss; positive means the model is better.
            - Calibration error checks whether confidence lines up with actual win rate.
            - A simulated flat-stake bet is placed when the model's implied probability **exceeds** the
              Bet365 market's implied probability by more than **5 percentage points** (the edge threshold).
            - ROI is computed as `(total returns − total staked) / total staked`.
            - CLV compares the taken price against closing odds when closing odds are available.
            - **Bet365 odds** are sourced from football-data.co.uk (`B365H/D/A` columns).
            - No bet is placed when the model has no edge over the market.
            """
        )
else:
    st.info(
        "Backtest results not found. "
        "Run `python backtest.py` locally or wait for the next nightly pipeline."
    )
