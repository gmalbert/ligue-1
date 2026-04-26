"""Team Deep Dive page."""

from os import path

import pandas as pd
import streamlit as st

from utils import get_dataframe_height, render_table, load_historical_data

HIST_PATH = "data_files/combined_historical_data.csv"

st.title("🔬 Team Deep Dive")

if not path.exists(HIST_PATH):
    st.info("Run `python fetch_historical_csvs.py` to enable Team Deep Dive.")
    st.stop()

hist_df = load_historical_data(HIST_PATH)
all_teams = sorted(set(hist_df["HomeTeam"].dropna()) | set(hist_df["AwayTeam"].dropna()))

selected = st.selectbox("Select a team:", all_teams)

home_m = hist_df[hist_df["HomeTeam"] == selected]
away_m = hist_df[hist_df["AwayTeam"] == selected]
total  = len(home_m) + len(away_m)

if total == 0:
    st.info(f"No match data found for {selected}.")
    st.stop()

# ── KPI Row ────────────────────────────────────────────────────────────────
wins   = int((home_m["FullTimeResult"] == "H").sum() + (away_m["FullTimeResult"] == "A").sum())
draws  = int((home_m["FullTimeResult"] == "D").sum() + (away_m["FullTimeResult"] == "D").sum())
losses = total - wins - draws
goals_for     = int(home_m["FullTimeHomeGoals"].sum() + away_m["FullTimeAwayGoals"].sum())
goals_against = int(home_m["FullTimeAwayGoals"].sum() + away_m["FullTimeHomeGoals"].sum())

k1, k2, k3, k4, k5, k6, k7 = st.columns(7)
k1.metric("Matches",   total)
k2.metric("Wins",      wins)
k3.metric("Draws",     draws)
k4.metric("Losses",    losses)
k5.metric("Win Rate",  f"{wins / total:.1%}")
k6.metric("Goals For", goals_for)
k7.metric("GD",        goals_for - goals_against)

st.divider()

# ── Home / Away Split ─────────────────────────────────────────────────────
st.subheader("🏠 Home vs ✈️ Away Split")
sp1, sp2 = st.columns(2)

with sp1:
    st.markdown(f"**Home** ({len(home_m)} matches)")
    if len(home_m) > 0:
        hw = (home_m["FullTimeResult"] == "H").sum()
        hd = (home_m["FullTimeResult"] == "D").sum()
        hl = (home_m["FullTimeResult"] == "A").sum()
        hg_for  = home_m["FullTimeHomeGoals"].sum()
        hg_ag   = home_m["FullTimeAwayGoals"].sum()
        sh1, sh2, sh3, sh4 = st.columns(4)
        sh1.metric("Wins",     int(hw))
        sh2.metric("Draws",    int(hd))
        sh3.metric("Losses",   int(hl))
        sh4.metric("Win Rate", f"{hw / len(home_m):.1%}")
        st.caption(f"Goals: {int(hg_for)} for · {int(hg_ag)} against")

with sp2:
    st.markdown(f"**Away** ({len(away_m)} matches)")
    if len(away_m) > 0:
        aw = (away_m["FullTimeResult"] == "A").sum()
        ad = (away_m["FullTimeResult"] == "D").sum()
        al = (away_m["FullTimeResult"] == "H").sum()
        ag_for  = away_m["FullTimeAwayGoals"].sum()
        ag_ag   = away_m["FullTimeHomeGoals"].sum()
        sa1, sa2, sa3, sa4 = st.columns(4)
        sa1.metric("Wins",     int(aw))
        sa2.metric("Draws",    int(ad))
        sa3.metric("Losses",   int(al))
        sa4.metric("Win Rate", f"{aw / len(away_m):.1%}")
        st.caption(f"Goals: {int(ag_for)} for · {int(ag_ag)} against")

st.divider()

# ── Last 10 Results ────────────────────────────────────────────────────────
st.subheader("📋 Last 10 Results")

home_m2 = home_m.copy().assign(
    Venue="Home",
    GoalsFor=home_m["FullTimeHomeGoals"],
    GoalsAgainst=home_m["FullTimeAwayGoals"],
    Outcome=home_m["FullTimeResult"].map({"H": "Win", "D": "Draw", "A": "Loss"}),
)
away_m2 = away_m.copy().assign(
    Venue="Away",
    GoalsFor=away_m["FullTimeAwayGoals"],
    GoalsAgainst=away_m["FullTimeHomeGoals"],
    Outcome=away_m["FullTimeResult"].map({"A": "Win", "D": "Draw", "H": "Loss"}),
)

recent = (
    pd.concat([home_m2, away_m2])
    .sort_values("MatchDate", ascending=False)
    .head(10)
)

show_cols = ["MatchDate", "HomeTeam", "FullTimeHomeGoals", "FullTimeAwayGoals",
             "AwayTeam", "FullTimeResult", "Venue", "Outcome"]
show_cols = [c for c in show_cols if c in recent.columns]

def _outcome_style(val: str) -> str:
    import streamlit as st
    dark = st.session_state.get("dark_mode", True)
    if dark:
        return {
            "Win":  "background-color: rgba(46,204,113,0.2)",
            "Draw": "background-color: rgba(243,156,18,0.2)",
            "Loss": "background-color: rgba(231,76,60,0.2)",
        }.get(val, "")
    else:
        return {
            "Win":  "background-color: #d4edda; color: #0a3a1a",
            "Draw": "background-color: #fff3cd; color: #3a2800",
            "Loss": "background-color: #cce5ff; color: #0a1e3a",
        }.get(val, "background-color: #f0f8ff; color: #0a1428")

styled = recent[show_cols].rename(columns={
    "MatchDate": "Date", "FullTimeHomeGoals": "HG",
    "FullTimeAwayGoals": "AG", "FullTimeResult": "FTR",
}).style.map(_outcome_style, subset=["Outcome"])

render_table(styled, hide_index=True, use_container_width=True)
