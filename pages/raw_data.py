"""Raw Data browser page."""

from os import path

import pandas as pd
import streamlit as st

from utils import get_dataframe_height, render_table, load_historical_data

HIST_PATH = "data_files/combined_historical_data.csv"

st.title("📁 Raw Data")
st.caption("Browse the full historical La Liga match dataset.")

if not path.exists(HIST_PATH):
    st.warning(f"`{HIST_PATH}` not found.")
    st.info("Run `python fetch_historical_csvs.py` to download 10 seasons of La Liga results.")
    st.stop()

df = load_historical_data(HIST_PATH)
df = df.sort_values("MatchDate", ascending=False).reset_index(drop=True)

# ── Filters ────────────────────────────────────────────────────────────────
fc1, fc2, fc3 = st.columns(3)

with fc1:
    seasons = sorted(df["Season"].dropna().unique(), reverse=True) if "Season" in df.columns else []
    season_filter = st.selectbox("Season", ["All seasons"] + list(seasons))

all_teams = sorted(set(df["HomeTeam"].dropna()) | set(df["AwayTeam"].dropna()))
with fc2:
    team_filter = st.selectbox("Team", ["All teams"] + all_teams)

with fc3:
    result_filter = st.selectbox("Result", ["All", "H — Home Win", "D — Draw", "A — Away Win"])

# Apply filters
if season_filter != "All seasons" and "Season" in df.columns:
    df = df[df["Season"] == season_filter]

if team_filter != "All teams":
    df = df[(df["HomeTeam"] == team_filter) | (df["AwayTeam"] == team_filter)]

if result_filter.startswith("H"):
    df = df[df["FullTimeResult"] == "H"]
elif result_filter.startswith("D"):
    df = df[df["FullTimeResult"] == "D"]
elif result_filter.startswith("A"):
    df = df[df["FullTimeResult"] == "A"]

# ── Display ────────────────────────────────────────────────────────────────
st.write(f"**{len(df):,} matches** · {df['HomeTeam'].nunique() if 'HomeTeam' in df.columns else '?'} teams")

# Priority columns
priority = [
    "MatchDate", "HomeTeam", "FullTimeHomeGoals", "FullTimeAwayGoals", "AwayTeam",
    "FullTimeResult", "Season",
    "OddsHome", "OddsDraw", "OddsAway",
    "HomeGoals_Avg_L5", "AwayGoals_Avg_L5",
    "HomeWinRate_L10", "AwayWinRate_L10",
    "ImpliedProb_HomeWin", "ImpliedProb_Draw", "ImpliedProb_AwayWin",
]
display_cols = [c for c in priority if c in df.columns]
if not display_cols:
    display_cols = list(df.columns)

rename_map = {
    "MatchDate":           "Date",
    "FullTimeHomeGoals":   "HG",
    "FullTimeAwayGoals":   "AG",
    "FullTimeResult":      "FTR",
    "HomeGoals_Avg_L5":    "Home Gls L5",
    "AwayGoals_Avg_L5":    "Away Gls L5",
    "HomeWinRate_L10":     "Home Win% L10",
    "AwayWinRate_L10":     "Away Win% L10",
    "ImpliedProb_HomeWin": "Mkt Home",
    "ImpliedProb_Draw":    "Mkt Draw",
    "ImpliedProb_AwayWin": "Mkt Away",
    "OddsHome":            "B365 H",
    "OddsDraw":            "B365 D",
    "OddsAway":            "B365 A",
}

render_table(
    df[display_cols].rename(columns=rename_map),
    hide_index=True,
    width='stretch',
    height=get_dataframe_height(df),
)

# ── Download ───────────────────────────────────────────────────────────────
csv_bytes = df[display_cols].to_csv(index=False).encode("utf-8")
st.download_button(
    label="📥 Download filtered data as CSV",
    data=csv_bytes,
    file_name="la_liga_raw_data.csv",
    mime="text/csv",
    width='stretch',
)

st.divider()

# ── Data Dictionary ────────────────────────────────────────────────────────
with st.expander("📖 Data Dictionary"):
    st.markdown(
        """
| Column | Description |
|---|---|
| **Date** | Match date |
| **HomeTeam / AwayTeam** | Canonical club names |
| **HG / AG** | Full-time goals for home / away |
| **FTR** | Full-time result: H = Home win · D = Draw · A = Away win |
| **Season** | La Liga season (e.g. `2023-24`) |
| **Home Gls L5** | Rolling 5-game avg goals scored (home team, previous matches) |
| **Away Gls L5** | Rolling 5-game avg goals scored (away team) |
| **Home Win% L10** | Rolling 10-game win rate (all venues) |
| **Mkt Home / Draw / Away** | Vig-removed bookmaker implied probability |
| **B365 H / D / A** | Raw Bet365 decimal odds |
        """
    )
