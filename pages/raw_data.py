"""Raw Data browser page."""

from os import path

import pandas as pd
import streamlit as st

from utils import get_dataframe_height, render_table, load_historical_data

HIST_PATH = "data_files/combined_historical_data.csv"

st.title("📁 Raw Data")
st.caption("Browse the full historical Ligue 1 match dataset.")

if not path.exists(HIST_PATH):
    st.warning(f"`{HIST_PATH}` not found.")
    st.info("Run `python fetch_historical_csvs.py` to download 10 seasons of Ligue 1 results.")
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

display_df = df[display_cols].rename(columns=rename_map).copy()
if "Date" in display_df.columns:
    display_df["Date"] = pd.to_datetime(display_df["Date"], errors="coerce").dt.strftime("%Y-%m-%d")
if "Time" in display_df.columns:
    display_df["Time"] = display_df["Time"].replace(
        {"00:00:00": "", "00:00:00:00": "", "0:00": "", "00:00": ""}
    )

render_table(
    display_df,
    hide_index=True,
    width='stretch',
    height=get_dataframe_height(df),
)

# ── Download ───────────────────────────────────────────────────────────────
csv_bytes = df[display_cols].to_csv(index=False).encode("utf-8")
st.download_button(
    label="📥 Download filtered data as CSV",
    data=csv_bytes,
    file_name="ligue1_raw_data.csv",
    mime="text/csv",
    width='stretch',
)

st.divider()

# ── Data Dictionary ────────────────────────────────────────────────────────
with st.expander("📖 Data Dictionary", expanded=False):
    dictionary_rows = [
        ("Date", "Match date."),
        ("HomeTeam", "Home club name in the canonical football-data.co.uk format."),
        ("AwayTeam", "Away club name in the canonical football-data.co.uk format."),
        ("HG", "Full-time goals scored by the home team."),
        ("AG", "Full-time goals scored by the away team."),
        ("FTR", "Full-time result: H = home win, D = draw, A = away win."),
        ("Season", "Ligue 1 season label, such as 2024-25."),
        ("B365 H", "Bet365 decimal odds for a home win."),
        ("B365 D", "Bet365 decimal odds for a draw."),
        ("B365 A", "Bet365 decimal odds for an away win."),
        ("Home Gls L5", "Home team's average goals scored over its previous 5 matches."),
        ("Away Gls L5", "Away team's average goals scored over its previous 5 matches."),
        ("Home Win% L10", "Home team's win rate over its previous 10 matches, all venues."),
        ("Away Win% L10", "Away team's win rate over its previous 10 matches, all venues."),
        ("Mkt Home", "Vig-removed market implied probability for a home win."),
        ("Mkt Draw", "Vig-removed market implied probability for a draw."),
        ("Mkt Away", "Vig-removed market implied probability for an away win."),
    ]
    dictionary_df = pd.DataFrame(dictionary_rows, columns=["Column", "Description"])
    render_table(dictionary_df, hide_index=True, width="stretch")
