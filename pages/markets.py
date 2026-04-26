"""Markets page — bookmaker odds, implied probabilities, EV comparison."""

from os import path

import pandas as pd
import streamlit as st

from utils import get_dataframe_height, render_table

ODDS_PATH = "data_files/raw/odds.csv"

st.title("📈 Markets")
st.caption("Bookmaker odds and vig-removed implied probabilities for upcoming La Liga fixtures.")

if not path.exists(ODDS_PATH):
    st.warning("Odds data is not yet available — it is refreshed nightly.")
    st.stop()

df = pd.read_csv(ODDS_PATH)
if df.empty:
    st.info("Odds data is not yet available — check back after the next nightly update.")
    st.stop()

# ── Filters ────────────────────────────────────────────────────────────────
fc1, fc2 = st.columns(2)

bookmakers = sorted(df["Bookmaker"].dropna().unique()) if "Bookmaker" in df.columns else []
if bookmakers:
    with fc1:
        selected_bm = st.selectbox("Bookmaker", ["All"] + bookmakers)
    if selected_bm != "All":
        df = df[df["Bookmaker"] == selected_bm]

teams_in_odds = sorted(
    set(df.get("HomeTeam", pd.Series(dtype=str)).dropna()) |
    set(df.get("AwayTeam", pd.Series(dtype=str)).dropna())
)
if teams_in_odds:
    with fc2:
        team_filter = st.selectbox("Team", ["All teams"] + teams_in_odds)
    if team_filter != "All teams":
        df = df[
            (df.get("HomeTeam", "") == team_filter) |
            (df.get("AwayTeam", "") == team_filter)
        ]

st.caption(f"Showing {len(df)} lines")
render_table(df, hide_index=True, width='stretch', height=get_dataframe_height(df))

# ── Implied probability guide ──────────────────────────────────────────────
with st.expander("ℹ️ How implied probabilities work"):
    st.markdown(
        """
Implied probabilities are derived from bookmaker odds with the vig (overround) removed:

$$P_{\\text{implied}} = \\frac{1/\\text{odds}}{1/\\text{odds}_H + 1/\\text{odds}_D + 1/\\text{odds}_A}$$

A market implied prob **higher** than the model's prediction means the book has priced that outcome
too cheaply — potential value play. See **Best Bets** for plays that exceed the threshold.
        """
    )
