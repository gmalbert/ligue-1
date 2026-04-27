"""Best Bets page — value plays where model edge exceeds the EV threshold."""

from os import path

import pandas as pd
import streamlit as st

from utils import render_table

EV_THRESHOLD = 0.04   # Minimum model-vs-market edge to surface a play

PRED_PATH = "data_files/predictions_log.csv"
ODDS_PATH = "data_files/raw/odds.csv"

st.title("💰 Best Bets")
st.caption(
    f"Plays where the model's probability exceeds the market implied probability "
    f"by ≥ {EV_THRESHOLD:.0%}. Not financial advice."
)

if not path.exists(PRED_PATH) or not path.exists(ODDS_PATH):
    missing = []
    if not path.exists(PRED_PATH):
        missing.append("Predictions (`data_files/predictions_log.csv`) — generated nightly")
    if not path.exists(ODDS_PATH):
        missing.append("Odds (`data_files/raw/odds.csv`) — fetched nightly")

    st.info("The following data is not yet available (updated nightly):\n\n" + "\n".join(f"- {m}" for m in missing))
    st.stop()

preds = pd.read_csv(PRED_PATH)
odds  = pd.read_csv(ODDS_PATH)

# Normalise date column name so the merge key is consistent
if "MatchDate" in preds.columns and "Date" not in preds.columns:
    preds = preds.rename(columns={"MatchDate": "Date"})

if preds.empty or odds.empty:
    st.info("Predictions or odds file is empty.")
    st.stop()

# ── Merge on HomeTeam + AwayTeam + Date ────────────────────────────────────
merge_cols = [c for c in ["HomeTeam", "AwayTeam", "Date"] if c in preds.columns and c in odds.columns]
if not merge_cols:
    st.error("Cannot merge predictions and odds — no shared key columns (HomeTeam, AwayTeam, Date).")
    st.stop()

merged = preds.merge(odds, on=merge_cols, how="inner", suffixes=("_pred", "_odds"))

# ── Compute edge for each outcome ─────────────────────────────────────────
outcome_map = [
    ("Home Win", "PredHomeWin", "ImpliedProb_HomeWin", "HomeWinOdds"),
    ("Draw",     "PredDraw",    "ImpliedProb_Draw",    "DrawOdds"),
    ("Away Win", "PredAwayWin", "ImpliedProb_AwayWin", "AwayWinOdds"),
]

rows = []
for _, row in merged.iterrows():
    for outcome, pred_col, mkt_col, odds_col in outcome_map:
        pred_p = row.get(pred_col)
        mkt_p  = row.get(mkt_col)
        if pd.isna(pred_p) or pd.isna(mkt_p):
            continue
        edge = float(pred_p) - float(mkt_p)
        if edge >= EV_THRESHOLD:
            rows.append({
                "Date":        row.get("Date", ""),
                "Match":       f"{row.get('HomeTeam','')} vs {row.get('AwayTeam','')}",
                "Bet":         outcome,
                "Model":       f"{float(pred_p):.1%}",
                "Market":      f"{float(mkt_p):.1%}",
                "Edge":        f"+{edge:.1%}",
                "Odds":        row.get(odds_col, "—"),
                "Bookmaker":   row.get("Bookmaker", "—"),
                "_edge_raw":   edge,
            })

if not rows:
    st.success(f"No value plays found with edge ≥ {EV_THRESHOLD:.0%} right now. Check back after odds update.")
    st.stop()

bets_df = pd.DataFrame(rows).sort_values("_edge_raw", ascending=False).drop(columns=["_edge_raw"])

st.success(f"✅ {len(bets_df)} value play{'s' if len(bets_df) != 1 else ''} found (edge ≥ {EV_THRESHOLD:.0%})")

render_table(bets_df, hide_index=True, width='stretch')

# ── Edge threshold slider ──────────────────────────────────────────────────
st.divider()
new_threshold = st.slider(
    "Adjust minimum edge threshold",
    min_value=0.01,
    max_value=0.15,
    value=EV_THRESHOLD,
    step=0.01,
    format="%.0f%%",
)
if new_threshold != EV_THRESHOLD:
    st.info(f"Showing plays with edge ≥ {new_threshold:.0%} — reload page to apply permanently.")

with st.expander("ℹ️ How edge is calculated"):
    st.markdown(
        """
**Edge = Model Probability − Market Implied Probability**

Where market implied probability = $\\frac{1/\\text{odds}}{\\text{total book overround}}$

A positive edge suggests the bookmaker has underpriced the outcome relative to the model's estimate.
Always use proper bankroll management and bet sizing.
        """
    )
