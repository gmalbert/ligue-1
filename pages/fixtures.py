"""Fixtures & Standings page."""

from datetime import datetime
from os import path

import pandas as pd
import streamlit as st

from utils import (
    compute_la_liga_standings,
    compute_league_stats,
    get_dataframe_height,
    load_historical_data,
    load_upcoming_fixtures,
    render_table,
)

HIST_PATH     = "data_files/combined_historical_data.csv"
FIXTURES_PATH = "data_files/upcoming_fixtures.csv"
WEATHER_PATH  = "data_files/raw/match_weather.csv"

st.title("🗓️ Fixtures & Standings")


# ── Season stats banner ────────────────────────────────────────────────────
season_year = int(st.session_state.get("selected_season", "2025-26").split("-")[0]) + 1
stats = compute_league_stats(HIST_PATH, season_year)
if stats and stats["n"] > 0:
    with st.expander(f"📈 Ligue 1 {season_year - 1}-{str(season_year)[2:]} Stats — {stats['n']} matches played", expanded=False):
        s1, s2, s3, s4, s5, s6 = st.columns(6)
        s1.metric("Home Win %",   f"{stats['home_win_pct']:.0%}")
        s2.metric("Draw %",       f"{stats['draw_pct']:.0%}")
        s3.metric("Away Win %",   f"{stats['away_win_pct']:.0%}")
        s4.metric("Avg Goals",    f"{stats['avg_total_goals']:.2f}")
        s5.metric("BTTS",         f"{stats['btts_pct']:.0%}")
        s6.metric("Over 2.5",     f"{stats['over_2_5_pct']:.0%}")
    st.divider()


# ── Standings ──────────────────────────────────────────────────────────────
if path.exists(HIST_PATH):
    hist_df = load_historical_data(HIST_PATH)
    season_start = f"{season_year - 1}-08-01"
    standings = compute_la_liga_standings(hist_df, season_start=season_start)

    if not standings.empty:
        st.subheader(f"📊 Ligue 1 Table — {season_year - 1}-{str(season_year)[2:]}")
        render_table(standings, hide_index=True, width='stretch',
                     height=get_dataframe_height(standings, max_height=760))
        st.divider()
    else:
        st.info("No results found for the current season yet.")
else:
    st.info("Run `python fetch_historical_csvs.py` to populate the standings table.")


# ── Upcoming fixtures ──────────────────────────────────────────────────────
st.subheader("🗓️ Upcoming Ligue 1 Fixtures")
st.caption("*Times in Eastern Time (ET)*")

if not path.exists(FIXTURES_PATH):
    st.warning("No upcoming fixtures — data is refreshed nightly via GitHub Actions.")
    st.stop()

upcoming = load_upcoming_fixtures(FIXTURES_PATH)
if upcoming.empty:
    st.info("Fixtures file is empty — data is refreshed nightly.")
    st.stop()

st.caption(
    f"Last updated: {datetime.fromtimestamp(path.getmtime(FIXTURES_PATH)).strftime('%Y-%m-%d %H:%M')}"
)

# Load weather if available
weather_df: pd.DataFrame | None = None
if path.exists(WEATHER_PATH):
    try:
        weather_df = pd.read_csv(WEATHER_PATH)
        weather_df["Date"] = weather_df["Date"].astype(str).str[:10]
    except Exception:
        weather_df = None

# ── Weather icons map ──────────────────────────────────────────────────────
WEATHER_ICONS = {
    "Clear":        "☀️",
    "Partly cloudy":"⛅",
    "Foggy":        "🌫️",
    "Rainy":        "🌧️",
    "Snowy":        "❄️",
    "Showers":      "🌦️",
    "Thunderstorm": "⛈️",
}

for _, fix in upcoming.iterrows():
    home = str(fix.get("HomeTeam", "?"))
    away = str(fix.get("AwayTeam", "?"))
    date = str(fix.get("Date", ""))[:10]
    time = str(fix.get("Time", ""))
    mday = fix.get("Matchday", "—")
    label = f"**{home}** vs **{away}**  —  {date}  {time}"
    with st.expander(label, expanded=False):
        c1, c2, c3 = st.columns([2, 1, 2])
        c1.markdown(f"### 🏠 {home}")
        c2.markdown("### VS")
        c3.markdown(f"### ✈️ {away}")
        st.caption(f"Matchday {mday} · 🌱 Natural Grass · 🇫🇷 Ligue 1")

        # Weather info
        if weather_df is not None:
            w_row = weather_df[
                (weather_df["HomeTeam"] == home) & (weather_df["Date"] == date)
            ]
            if not w_row.empty:
                w = w_row.iloc[0]
                desc  = str(w.get("WeatherDesc", "N/A"))
                icon  = WEATHER_ICONS.get(desc, "🌡️")
                temp  = w.get("TempMaxC")
                rain  = w.get("PrecipMM")
                wind  = w.get("WindKmh")
                parts = [f"{icon} {desc}"]
                if temp is not None:
                    parts.append(f"🌡️ {temp:.0f}°C")
                if rain is not None:
                    parts.append(f"💧 {rain:.1f} mm")
                if wind is not None:
                    parts.append(f"💨 {wind:.0f} km/h")
                st.caption("  ·  ".join(parts))