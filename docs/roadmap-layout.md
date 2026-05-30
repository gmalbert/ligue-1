# Layout Roadmap — Ligue Odds

## Status
- ✅ Primary Streamlit layout and multi-page navigation are implemented for Ligue Odds.
- 🟡 Partial: the roadmap examples still use old La Liga file names in places; the current app uses `predictions.py` plus `pages/*.py`.
- ⚪ Outstanding: sidebar refresh button and cleanup of legacy La Liga naming in docs/code aliases.
- Reviewed: 2026-05-28

## Current Implementation Status

| Area | Status |
|---|---|
| App entry point and page config | ✅ Implemented in `predictions.py` |
| Sidebar logo, season selector, theme toggle, and countdown | ✅ Implemented in `predictions.py` |
| Sidebar refresh button | ⚪ Not implemented |
| Streamlit `st.navigation` multi-page layout | ✅ Implemented in `predictions.py` |
| Fixtures & standings page | ✅ Implemented in `pages/fixtures.py` |
| Predictions page | ✅ Implemented in `pages/predictions_tab.py` |
| Statistics page | ✅ Implemented in `pages/statistics.py` |
| Team deep dive page | ✅ Implemented in `pages/team_deep_dive.py` |
| Raw data page | ✅ Implemented in `pages/raw_data.py` |
| Markets page | ✅ Implemented in `pages/markets.py` |
| Best Bets page | ✅ Implemented in `pages/best_bets.py` |
| Performance page | ✅ Implemented in `pages/performance.py` |
| Shared footer and theme helpers | ✅ Implemented in `footer.py` and `themes.py` |

## Overview

Ligue Odds uses Streamlit's multi-page navigation with prediction, fixture, statistics, team deep dive, raw data, markets, best bets, and performance pages. The visual style follows the Betting Oracle suite: wide layout, sidebar logo, day/night theming, and a shared footer.

---

## Page Structure

```
predictions.py          ← Main Streamlit entry point
pages/
  predictions_tab.py    ← Default predictions page
  fixtures.py           ← Fixtures and standings
  statistics.py         ← xG proxy, form, H2H, congestion, importance
  team_deep_dive.py     ← Team-level breakdown
  raw_data.py           ← Historical data browser
  markets.py            ← Odds comparison
  best_bets.py          ← Top model-vs-market value plays
  performance.py        ← Accuracy, log, and backtest dashboard
```

---

## 1. App Entry Point & Page Config

```python
# la_liga_linea.py — top of file

import streamlit as st
import os
import warnings
from os import path
from datetime import datetime

from footer import add_betting_oracle_footer
from themes import apply_theme

warnings.filterwarnings("ignore")

st.set_page_config(
    page_title="La Liga Linea",
    page_icon="🇪🇸",          # Spanish flag — differentiates from EPL ⚽ and MLS
    layout="wide",
    initial_sidebar_state="expanded",
)
```

---

## 2. Sidebar — Logo, Navigation & Controls

```python
# ── Sidebar logo
_logo_path = path.join("data_files", "logo.png")
if path.exists(_logo_path):
    st.sidebar.image(_logo_path, width=220)
else:
    st.sidebar.markdown("## 🇪🇸 La Liga Linea")

# ── Sidebar: next match countdown
def next_match_countdown(upcoming_df) -> str | None:
    if upcoming_df is None or upcoming_df.empty:
        return None
    try:
        upcoming_df = upcoming_df.copy()
        upcoming_df["DateTime"] = pd.to_datetime(
            upcoming_df["Date"] + " " + upcoming_df.get("Time", "12:00 PM ET"),
            errors="coerce",
        )
        next_m = upcoming_df.dropna(subset=["DateTime"]).sort_values("DateTime").iloc[0]
        delta = next_m["DateTime"] - datetime.now()
        if delta.total_seconds() <= 0:
            return None
        d, h = delta.days, delta.seconds // 3600
        m = (delta.seconds % 3600) // 60
        return f"⏱️ Next: **{next_m['HomeTeam']} vs {next_m['AwayTeam']}**\n{d}d {h}h {m}m"
    except Exception:
        return None

countdown = next_match_countdown(upcoming_df if 'upcoming_df' in dir() else None)
if countdown:
    st.sidebar.info(countdown)

# ── Sidebar: data refresh button
st.sidebar.subheader("Data")
if st.sidebar.button("🔄 Refresh Fixtures"):
    import subprocess
    with st.spinner("Fetching fixtures…"):
        result = subprocess.run(["python", "fetch_upcoming_fixtures.py"], capture_output=True)
    if result.returncode == 0:
        st.sidebar.success("✅ Fixtures updated!")
        st.rerun()
    else:
        st.sidebar.error("❌ Update failed")

# ── Sidebar: season selector
selected_season = st.sidebar.selectbox(
    "Season",
    options=["2025-26", "2024-25", "2023-24", "2022-23", "2021-22"],
    index=0,
)
```

---

## 3. Multi-Page Navigation (Streamlit `st.navigation`)

```python
# ── Navigation at the bottom of la_liga_linea.py

apply_theme()

pg = st.navigation(
    {
        "": [
            st.Page(home_page, title="La Liga Linea", icon="🇪🇸", default=True),
        ],
        "Markets": [
            st.Page("pages/6_Markets.py",   title="Markets",   icon="📊"),
            st.Page("pages/7_Best_Bets.py", title="Best Bets", icon="💰"),
        ],
    }
)
pg.run()

# ── Footer (shown on every page)
add_betting_oracle_footer()
```

---

## 4. Main Page — 5-Tab Layout

```python
def home_page() -> None:
    st.title("🇪🇸 La Liga Linea")

    # Last-updated caption
    fixtures_file = "data_files/upcoming_fixtures.csv"
    if path.exists(fixtures_file):
        last_updated = datetime.fromtimestamp(os.path.getmtime(fixtures_file))
        st.caption("Last updated: " + last_updated.strftime("%Y-%m-%d %I:%M %p ET"))

    tab1, tab2, tab3, tab4, tab5 = st.tabs([
        "🗓️ Upcoming Matches",
        "🎯 Upcoming Predictions",
        "📊 Statistics",
        "🔬 Team Deep Dive",
        "📁 Raw Data",
    ])

    with tab1:
        _tab_upcoming_matches()

    with tab2:
        _tab_predictions()

    with tab3:
        _tab_statistics()

    with tab4:
        _tab_deep_dive()

    with tab5:
        _tab_raw_data()
```

---

## 5. Tab 1 — Upcoming Matches Layout

```python
def _tab_upcoming_matches():
    # Season stats expander (collapsible banner)
    league_stats = compute_league_stats("data_files/combined_historical_data.csv", 2026)
    if league_stats:
        with st.expander(f"📈 La Liga 2025-26 Season Stats ({league_stats['n']} matches)", expanded=False):
            s1, s2, s3, s4, s5, s6 = st.columns(6)
            s1.metric("Home Win %", f"{league_stats['home_win_pct']:.0%}")
            s2.metric("Draw %",     f"{league_stats['draw_pct']:.0%}")
            s3.metric("Away Win %", f"{league_stats['away_win_pct']:.0%}")
            s4.metric("Avg Goals",  f"{league_stats['avg_total_goals']:.2f}")
            s5.metric("BTTS",       f"{league_stats['btts_pct']:.0%}")
            s6.metric("Over 2.5",   f"{league_stats['over_2_5_pct']:.0%}")
        st.divider()

    # Live scores toggle
    if st.toggle("🔴 Live Scores"):
        live_df = fetch_live_la_liga_scores()
        if not live_df.empty:
            st.subheader("Live La Liga Matches")
            st.dataframe(live_df, hide_index=True)
        else:
            st.info("No matches currently in progress.")
        st.divider()

    # Current standings
    csv_path = "data_files/combined_historical_data.csv"
    if path.exists(csv_path):
        df_main = load_historical_data(csv_path)
        standings = compute_la_liga_standings(df_main)
        if not standings.empty:
            st.subheader("📊 La Liga Table")
            st.dataframe(standings, hide_index=True, height=get_dataframe_height(standings))
            st.divider()

    # Fixture cards
    st.subheader("🗓️ Upcoming La Liga Fixtures")
    st.caption("*Times shown in Eastern Time (ET)*")
    if not path.exists("data_files/upcoming_fixtures.csv"):
        st.warning("No upcoming fixtures. Run `python fetch_upcoming_fixtures.py`.")
        return

    upcoming = load_upcoming_fixtures("data_files/upcoming_fixtures.csv")
    for _, fix in upcoming.iterrows():
        home = str(fix.get("HomeTeam", "?"))
        away = str(fix.get("AwayTeam", "?"))
        label = f"**{home}** vs **{away}**  —  {fix.get('Date', '')} {fix.get('Time', '')}"
        with st.expander(label, expanded=False):
            c1, c2, c3 = st.columns([2, 1, 2])
            c1.markdown(f"**🏠 {home}**")
            c2.markdown("### VS")
            c3.markdown(f"**✈️ {away}**")
            st.caption(f"Matchday {fix.get('Matchday', '—')} · 🌱 Natural Grass")
```

---

## 6. Tab 2 — Predictions Layout

```python
def _tab_predictions():
    csv_path = "data_files/combined_historical_data.csv"
    fixtures_path = "data_files/upcoming_fixtures.csv"

    if not path.exists(csv_path):
        st.warning(f"Add `{csv_path}` to enable predictions.")
        return
    if not path.exists(fixtures_path):
        st.warning("Run `python fetch_upcoming_fixtures.py` first.")
        return

    # Model selector
    model_choice = st.radio(
        "Model:",
        ["Ensemble Classifier", "Poisson Regression"],
        horizontal=True,
    )

    with st.spinner("Training model…"):
        result = load_and_process_data(csv_path)
    if result[0] is None:
        st.warning("Could not parse historical data.")
        return

    X_train, X_test, y_train, y_test, feature_names, df_hist = result
    model = get_trained_model(X_train, y_train)
    y_pred = model.predict(X_test)
    acc = accuracy_score(y_test, y_pred)
    mae = mean_absolute_error(y_test, y_pred)

    # Model metric KPIs
    col1, col2, col3 = st.columns(3)
    col1.metric("Model Accuracy", f"{acc:.1%}", f"{acc - 0.5:.1%} vs random")
    col2.metric("Mean Absolute Error", f"{mae:.3f}")
    col3.metric("Test Predictions", len(y_test))
    st.divider()

    # Risk filter buttons
    st.subheader("🎯 Match Predictions with Risk Assessment")
    col_f1, col_f2, col_f3, col_f4 = st.columns(4)
    show_all  = col_f1.button("📊 All",          width='stretch')
    show_low  = col_f2.button("🟢 Low Risk",      width='stretch')
    show_mod  = col_f3.button("🟡 Moderate",      width='stretch')
    show_high = col_f4.button("🔴 High/Critical", width='stretch')

    # Build predictions DataFrame
    # ...build display_df with probabilities, risk, betting tips...

    # Color-coded risk rows
    if len(filtered) > 0:
        styled = filtered.style.apply(color_risk_rows, axis=1)
        st.dataframe(styled, width='stretch', hide_index=True,
                     height=get_dataframe_height(filtered))
    else:
        st.info("No matches for selected filter.")

    # Download button
    st.download_button(
        label="📥 Download as CSV",
        data=display_df.to_csv(index=False).encode("utf-8"),
        file_name=f"la_liga_predictions_{datetime.now().strftime('%Y%m%d')}.csv",
        mime="text/csv",
    )
```

---

## 7. Tab 3 — Statistics Layout

```python
def _tab_statistics():
    csv_path = "data_files/combined_historical_data.csv"
    st.subheader("📊 La Liga Statistics")

    # Sub-section: xG rankings from FBref
    st.markdown("### ⚽ Team xG Rankings (FBref)")
    fbref_path = "data_files/raw/fbref_team_xg.csv"
    if path.exists(fbref_path):
        xg_df = pd.read_csv(fbref_path)
        st.dataframe(
            xg_df.sort_values("xG", ascending=False),
            hide_index=True,
            height=get_dataframe_height(xg_df, max_height=500),
        )
    else:
        st.info("Run `python fetch_fbref_xg.py` to load xG data.")

    st.divider()

    if not path.exists(csv_path):
        st.info(f"Add `{csv_path}` to unlock historical statistics.")
        return

    df_stats = load_historical_data(csv_path)

    # Sub-section: team form
    st.markdown("### 📈 Recent Team Form (Last 5 Matches)")
    # ...form table with W/D/L emoji icons...

    st.divider()

    # Sub-section: head-to-head analyzer
    st.markdown("### 🏆 Head-to-Head Analyzer")
    h2h_teams = sorted(df_stats["HomeTeam"].dropna().unique())
    hc1, hc2 = st.columns(2)
    with hc1:
        t1 = st.selectbox("Team 1", h2h_teams, key="h2h_t1")
    with hc2:
        t2 = st.selectbox("Team 2", [t for t in h2h_teams if t != t1], key="h2h_t2")
    if st.button("🔍 Analyse H2H"):
        mask = (
            ((df_stats["HomeTeam"] == t1) & (df_stats["AwayTeam"] == t2)) |
            ((df_stats["HomeTeam"] == t2) & (df_stats["AwayTeam"] == t1))
        )
        h2h_df = df_stats[mask].sort_values("MatchDate", ascending=False).head(10)
        if len(h2h_df) > 0:
            st.success(f"{len(h2h_df)} meetings found.")
            st.dataframe(h2h_df[["MatchDate", "HomeTeam", "AwayTeam",
                                  "FullTimeHomeGoals", "FullTimeAwayGoals",
                                  "FullTimeResult"]], hide_index=True)
        else:
            st.info("No H2H data found.")

    st.divider()

    # Sub-section: Copa del Rey congestion
    st.markdown("### 🏆 Copa del Rey Congestion Flag")
    copa_path = "data_files/raw/copa_fixtures.csv"
    if path.exists(copa_path):
        copa_df = pd.read_csv(copa_path)
        copa_df["MatchDate"] = pd.to_datetime(copa_df["MatchDate"])
        recent_copa = copa_df[copa_df["MatchDate"] >= (pd.Timestamp.now() - pd.Timedelta(days=7))]
        if recent_copa.empty:
            st.info("No teams played Copa del Rey in the last 7 days.")
        else:
            st.warning(f"⚠️ {recent_copa['TeamName'].nunique()} teams played Copa del Rey in last 7 days.")
            st.dataframe(recent_copa, hide_index=True)
    else:
        st.info("Run `python fetch_copa_fixtures.py` to enable Copa congestion data.")
```

---

## 8. Tab 4 — Team Deep Dive Layout

```python
def _tab_deep_dive():
    csv_path = "data_files/combined_historical_data.csv"
    st.subheader("🔬 Team Deep Dive")

    all_teams_dd = _get_all_teams(csv_path)
    selected_team = st.selectbox("Select a team:", all_teams_dd, key="deep_dive_team")

    # KPI row
    k1, k2, k3 = st.columns(3)
    k1.metric("Surface", "🌱 Natural Grass")
    k2.metric("Competition", "La Liga (PD)")
    k3.metric("Country", "Spain 🇪🇸")

    st.divider()

    if path.exists(csv_path):
        df_dd = load_historical_data(csv_path)
        home_m = df_dd[df_dd["HomeTeam"] == selected_team]
        away_m = df_dd[df_dd["AwayTeam"] == selected_team]
        total  = len(home_m) + len(away_m)

        if total > 0:
            wins  = (home_m["FullTimeResult"] == "H").sum() + (away_m["FullTimeResult"] == "A").sum()
            draws = (home_m["FullTimeResult"] == "D").sum() + (away_m["FullTimeResult"] == "D").sum()
            losses = total - wins - draws
            hg    = home_m["FullTimeHomeGoals"].sum() + away_m["FullTimeAwayGoals"].sum()
            ga    = home_m["FullTimeAwayGoals"].sum() + away_m["FullTimeHomeGoals"].sum()

            m1, m2, m3, m4, m5, m6 = st.columns(6)
            m1.metric("Matches", total)
            m2.metric("Wins",    int(wins))
            m3.metric("Draws",   int(draws))
            m4.metric("Losses",  int(losses))
            m5.metric("Win Rate", f"{wins/total:.1%}")
            m6.metric("GD",      int(hg - ga))

        # Home vs away split
        st.markdown("**Home vs Away Split**")
        col_h, col_a = st.columns(2)
        with col_h:
            st.markdown(f"**Home:** {len(home_m)} matches")
            if len(home_m) > 0:
                hw = (home_m["FullTimeResult"] == "H").sum()
                st.metric("Home Win Rate", f"{hw/len(home_m):.1%}")
        with col_a:
            st.markdown(f"**Away:** {len(away_m)} matches")
            if len(away_m) > 0:
                aw = (away_m["FullTimeResult"] == "A").sum()
                st.metric("Away Win Rate", f"{aw/len(away_m):.1%}")

        # Last 10 results
        st.divider()
        st.markdown("**Last 10 Results**")
        all_team_m = pd.concat([
            home_m.assign(Venue="Home", GoalsFor=home_m["FullTimeHomeGoals"], GoalsAgainst=home_m["FullTimeAwayGoals"]),
            away_m.assign(Venue="Away", GoalsFor=away_m["FullTimeAwayGoals"], GoalsAgainst=away_m["FullTimeHomeGoals"]),
        ]).sort_values("MatchDate", ascending=False).head(10)
        st.dataframe(all_team_m[["MatchDate", "HomeTeam", "AwayTeam",
                                   "GoalsFor", "GoalsAgainst", "FullTimeResult", "Venue"]],
                     hide_index=True)
```

---

## 9. Tab 5 — Raw Data Layout

```python
def _tab_raw_data():
    csv_path = "data_files/combined_historical_data.csv"
    st.subheader("📁 Historical La Liga Match Data")

    if not path.exists(csv_path):
        st.warning(f"No data at `{csv_path}`. Run `python fetch_historical_csvs.py`.")
        return

    df_raw = load_historical_data(csv_path)
    df_raw = df_raw.sort_values("MatchDate", ascending=False)

    col_map = {
        "MatchDate":           "Date",
        "HomeTeam":            "Home Team",
        "AwayTeam":            "Away Team",
        "FullTimeHomeGoals":   "Home Goals",
        "FullTimeAwayGoals":   "Away Goals",
        "FullTimeResult":      "Result",
        "Season":              "Season",
        "HomexG_Avg_L5":       "Home xG L5",
        "AwayxG_Avg_L5":       "Away xG L5",
        "HomeGoals_Avg_L5":    "Home Goals L5",
        "AwayGoals_Avg_L5":    "Away Goals L5",
        "HomeMomentum_L3":     "Home Mom L3",
        "AwayMomentum_L3":     "Away Mom L3",
        "HomeRestDays":        "Home Rest",
        "AwayRestDays":        "Away Rest",
        "H2H_HomeWinRate_L5":  "H2H Home Win L5",
        "HomeCopaCongestion":  "Home Copa Flag",
        "AwayCopaCongestion":  "Away Copa Flag",
        "ImpliedProb_HomeWin": "Mkt Home Win",
        "ImpliedProb_Draw":    "Mkt Draw",
        "ImpliedProb_AwayWin": "Mkt Away Win",
    }
    priority = list(col_map.keys())
    display_cols = [c for c in priority if c in df_raw.columns]
    df_display = df_raw[display_cols].rename(columns=col_map)

    st.write(f"**{len(df_display):,} matches** in dataset")
    st.dataframe(df_display, height=get_dataframe_height(df_display), width='stretch', hide_index=True)

    # Data dictionary
    with st.expander("📖 Data Dictionary"):
        st.markdown("""
| Column | Description |
|---|---|
| **Date** | Match date (YYYY-MM-DD) |
| **Home / Away Team** | Club names (canonical La Liga format) |
| **Home / Away Goals** | Full-time goals |
| **Result** | H = Home win · D = Draw · A = Away win |
| **Season** | La Liga season (e.g. 2023-24) |
| **Home xG L5** | Rolling 5-game avg xG for home team (proxy until FBref integrated) |
| **Home Goals L5** | Rolling 5-game avg goals for home team |
| **Home Mom L3** | Sum of home goals in last 3 games (momentum proxy) |
| **Home Rest** | Days since home team's last match |
| **H2H Home Win L5** | Home team's win rate in last 5 H2H meetings |
| **Home Copa Flag** | 1 if home team played Copa del Rey in last 4 days |
| **Mkt Home Win** | Vig-removed market implied probability (home win) |
        """)
```

---

## 10. Markets Page (`pages/6_Markets.py`)

```python
# pages/6_Markets.py
import streamlit as st
import pandas as pd
from os import path

st.set_page_config(page_title="Markets — La Liga Linea", layout="wide", page_icon="📊")
st.title("📊 La Liga Markets")
st.caption("Bookmaker odds, implied probabilities, and model vs. market comparison.")

odds_path = "data_files/raw/odds.csv"
if not path.exists(odds_path):
    st.warning("No odds data found. Run `python fetch_odds.py`.")
    st.stop()

df_odds = pd.read_csv(odds_path)
bookmakers = df_odds["Bookmaker"].unique().tolist() if "Bookmaker" in df_odds.columns else []

if bookmakers:
    selected_bm = st.selectbox("Bookmaker", ["All"] + bookmakers)
    if selected_bm != "All":
        df_odds = df_odds[df_odds["Bookmaker"] == selected_bm]

st.dataframe(df_odds, width='stretch', hide_index=True)
```

---

## 11. Best Bets Page (`pages/7_Best_Bets.py`)

```python
# pages/7_Best_Bets.py
import streamlit as st
import pandas as pd
from os import path

st.set_page_config(page_title="Best Bets — La Liga Linea", layout="wide", page_icon="💰")
st.title("💰 La Liga Best Bets")
st.caption("Plays where the model's probability exceeds the market implied probability by the largest margin.")

EV_THRESHOLD = 0.04   # Only show plays where model edge ≥ 4%

# Load predictions + odds and compute EV
pred_path = "data_files/predictions_log.csv"
odds_path  = "data_files/raw/odds.csv"

if not path.exists(pred_path) or not path.exists(odds_path):
    st.info("Generate predictions and fetch odds to populate Best Bets.")
    st.stop()

preds = pd.read_csv(pred_path)
odds  = pd.read_csv(odds_path)

# Merge on HomeTeam + AwayTeam + Date
merged = preds.merge(odds, on=["HomeTeam", "AwayTeam", "Date"], how="inner")

rows = []
for _, row in merged.iterrows():
    for outcome, pred_col, mkt_col, odds_col in [
        ("Home Win", "PredHomeWin", "ImpliedProb_HomeWin", "HomeWinOdds"),
        ("Draw",     "PredDraw",    "ImpliedProb_Draw",    "DrawOdds"),
        ("Away Win", "PredAwayWin", "ImpliedProb_AwayWin", "AwayWinOdds"),
    ]:
        if pred_col not in row or mkt_col not in row:
            continue
        edge = row[pred_col] - row.get(mkt_col, row[pred_col])
        if edge >= EV_THRESHOLD:
            rows.append({
                "Date":          row["Date"],
                "Match":         f"{row['HomeTeam']} vs {row['AwayTeam']}",
                "Bet":           outcome,
                "Model Prob":    f"{row[pred_col]:.1%}",
                "Market Prob":   f"{row.get(mkt_col, 0):.1%}",
                "Edge":          f"+{edge:.1%}",
                "Odds":          row.get(odds_col, "—"),
                "Bookmaker":     row.get("Bookmaker", "—"),
            })

if rows:
    bets_df = pd.DataFrame(rows).sort_values("Edge", ascending=False)
    st.success(f"Found {len(bets_df)} value plays (edge ≥ {EV_THRESHOLD:.0%})")
    st.dataframe(bets_df, width='stretch', hide_index=True)
else:
    st.info(f"No plays found with edge ≥ {EV_THRESHOLD:.0%} against current lines.")
```

---

## 12. Shared Utilities

### `footer.py`
```python
# footer.py
import streamlit as st

def add_betting_oracle_footer():
    st.divider()
    st.markdown(
        """
        <div style='text-align:center;color:#888;font-size:0.8em;'>
        <strong>La Liga Linea</strong> — part of the Betting Oracle suite ·
        Predictions are for informational purposes only ·
        Gamble responsibly
        </div>
        """,
        unsafe_allow_html=True,
    )
```

### `themes.py`
```python
# themes.py
import streamlit as st

def apply_theme():
    st.markdown(
        """
        <style>
        /* La Liga brand red accent */
        [data-testid="stMetricValue"] { color: #EF0000; }
        [data-testid="stSidebar"] { background-color: #1a1a2e; }
        .stTabs [data-baseweb="tab-list"] { gap: 8px; }
        .stTabs [data-baseweb="tab"] {
            border-radius: 4px 4px 0 0;
            padding: 8px 16px;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )
```

### `.streamlit/config.toml`
```toml
[theme]
primaryColor = "#EF0000"        # La Liga red
backgroundColor = "#0e1117"
secondaryBackgroundColor = "#1a1a2e"
textColor = "#fafafa"
font = "sans serif"

[server]
headless = true
port = 8501
enableCORS = false
```

---

## 13. `requirements.txt`

```txt
streamlit>=1.36.0
pandas>=2.0.0
numpy>=1.24.0
xgboost>=2.0.0
scikit-learn>=1.3.0
scipy>=1.11.0
plotly>=5.18.0
requests>=2.31.0
beautifulsoup4>=4.12.0
lxml>=4.9.0
pytz>=2023.3
python-dotenv>=1.0.0
fpdf2>=2.7.0
torch>=2.0.0
schedule>=1.2.0
```

---

## Layout Design Principles

| Principle | Implementation |
|---|---|
| Familiarity | Same 5-tab structure as MLS Predictor and EPL apps |
| Color identity | La Liga red (`#EF0000`) as primary accent |
| Responsive tables | `get_dataframe_height()` helper caps at 600px |
| Progressive disclosure | Collapsible expanders for season stats banner, data dictionary |
| No clutter | Copa del Rey and Copa congestion are La Liga-only; no travel-distance UI needed |
| Betting safety | Footer disclaimer on every page |
