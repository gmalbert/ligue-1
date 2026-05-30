# Feature Roadmap — Ligue Odds

## Status
- ✅ Core app features are implemented for Ligue Odds.
- 🟡 Partial/adapted: Team Deep Dive, xG, and cup congestion are live but differ from the original La Liga examples.
- ⚪ Outstanding: live scores and PDF export.
- Reviewed: 2026-05-28

## Current Implementation Status

| # | Feature | Status |
|---|---|---|
| 1 | Upcoming fixtures | ✅ Implemented in `pages/fixtures.py` with Ligue 1 fixtures, ET kickoff display, and matchday cards |
| 2 | Season stats banner | ✅ Implemented in `pages/fixtures.py` via `utils.compute_league_stats()` |
| 3 | Current standings | ✅ Implemented in `pages/fixtures.py` via `utils.compute_league_standings()` |
| 4 | Upcoming predictions | ✅ Implemented in `pages/predictions_tab.py` from pre-generated prediction logs |
| 5 | Statistics tab | ✅ Implemented with xG proxy rankings, form, H2H, cup congestion, feature importance, and backtest summary |
| 6 | Team deep dive | 🟡 Implemented for KPIs, home/away split, and last 10 results; xG-per-team and cup-load details remain outstanding |
| 7 | Prediction performance tracker | ✅ Implemented with logging, validation, and `pages/performance.py` |
| 8 | Cup congestion flag | ✅ Adapted to Coupe de France via `fetch_copa_fixtures.py` and `prepare_model_data.py` |
| 9 | Live score integration | ⚪ Not implemented |
| 10 | PDF report export | ⚪ Not implemented |

---

## High Priority Features

### 1. Upcoming Fixtures Tab
**Priority:** High | **Effort:** Low | **Impact:** High

Display all upcoming La Liga fixtures with kickoff times (converted to Eastern Time), matchday number, and a season stats banner.

```python
# fetch_upcoming_fixtures.py
import requests
import pandas as pd
from datetime import datetime
import pytz

FOOTBALL_DATA_KEY = "your_football_data_org_key"
BASE_URL = "https://api.football-data.org/v4"
HEADERS = {"X-Auth-Token": FOOTBALL_DATA_KEY}

def fetch_upcoming_pd_fixtures() -> pd.DataFrame:
    """Fetch upcoming La Liga fixtures from football-data.org."""
    resp = requests.get(
        f"{BASE_URL}/competitions/PD/matches",
        headers=HEADERS,
        params={"status": "SCHEDULED"},
        timeout=15,
    )
    resp.raise_for_status()
    matches = resp.json().get("matches", [])

    rows = []
    et = pytz.timezone("America/New_York")
    for m in matches:
        utc_dt = datetime.fromisoformat(m["utcDate"].replace("Z", "+00:00"))
        et_dt = utc_dt.astimezone(et)
        rows.append({
            "Date": et_dt.strftime("%Y-%m-%d"),
            "Time": et_dt.strftime("%I:%M %p ET"),
            "Matchday": m.get("matchday"),
            "HomeTeam": m["homeTeam"]["name"],
            "AwayTeam": m["awayTeam"]["name"],
            "Status": m["status"],
        })

    df = pd.DataFrame(rows)
    df.to_csv("data_files/upcoming_fixtures.csv", index=False)
    print(f"Saved {len(df)} upcoming fixtures.")
    return df

if __name__ == "__main__":
    fetch_upcoming_pd_fixtures()
```

**UI Integration (in `la_liga_linea.py`):**
```python
import streamlit as st
import pandas as pd
from os import path

fixtures_file = "data_files/upcoming_fixtures.csv"

if path.exists(fixtures_file):
    last_updated = datetime.fromtimestamp(os.path.getmtime(fixtures_file))
    st.caption("Last updated: " + last_updated.strftime("%Y-%m-%d %I:%M %p ET"))

if not path.exists(fixtures_file):
    st.warning("No upcoming fixtures found. Run `python fetch_upcoming_fixtures.py`.")
else:
    upcoming = pd.read_csv(fixtures_file)
    st.subheader("🗓️ Upcoming La Liga Fixtures")
    st.caption("*Times shown in Eastern Time (ET)*")

    for _, fix in upcoming.iterrows():
        label = f"**{fix['HomeTeam']}** vs **{fix['AwayTeam']}**  —  {fix['Date']} {fix['Time']}"
        with st.expander(label, expanded=False):
            c1, c2, c3 = st.columns([2, 1, 2])
            c1.markdown(f"**🏠 {fix['HomeTeam']}**")
            c2.markdown("### VS")
            c3.markdown(f"**✈️ {fix['AwayTeam']}**")
            st.caption(f"Matchday {fix.get('Matchday', '—')}")
```

---

### 2. Season Stats Banner
**Priority:** High | **Effort:** Low | **Impact:** Medium

Show current-season league base rates: home win %, draw %, away win %, average goals, BTTS, over 2.5.

```python
# compute_league_stats in la_liga_linea.py
import streamlit as st
import pandas as pd

@st.cache_data(ttl=3600)
def compute_league_stats(csv_path: str, season_year: int) -> dict | None:
    if not path.exists(csv_path):
        return None
    df = pd.read_csv(csv_path)
    df["MatchDate"] = pd.to_datetime(df["MatchDate"], errors="coerce")
    df = df[df["MatchDate"].dt.year == season_year]
    if df.empty:
        return None

    res = df["FullTimeResult"]
    hg = pd.to_numeric(df.get("FullTimeHomeGoals", df.get("FTHG")), errors="coerce").fillna(0)
    ag = pd.to_numeric(df.get("FullTimeAwayGoals", df.get("FTAG")), errors="coerce").fillna(0)
    total = hg + ag
    n = len(df)

    return {
        "n": n,
        "home_win_pct": (res == "H").sum() / n,
        "draw_pct": (res == "D").sum() / n,
        "away_win_pct": (res == "A").sum() / n,
        "avg_total_goals": float(total.mean()),
        "btts_pct": float(((hg > 0) & (ag > 0)).sum() / n),
        "over_2_5_pct": float((total > 2.5).sum() / n),
        "over_1_5_pct": float((total > 1.5).sum() / n),
        "over_3_5_pct": float((total > 3.5).sum() / n),
        "clean_sheet_pct": float(((hg == 0) | (ag == 0)).sum() / n),
    }

# Display banner
league_stats = compute_league_stats("data_files/combined_historical_data.csv", 2026)
if league_stats:
    with st.expander(f"📈 La Liga {2026} Season Stats ({league_stats['n']} matches)", expanded=False):
        s1, s2, s3, s4, s5, s6 = st.columns(6)
        s1.metric("Home Win %", f"{league_stats['home_win_pct']:.0%}")
        s2.metric("Draw %",     f"{league_stats['draw_pct']:.0%}")
        s3.metric("Away Win %", f"{league_stats['away_win_pct']:.0%}")
        s4.metric("Avg Goals",  f"{league_stats['avg_total_goals']:.2f}")
        s5.metric("BTTS",       f"{league_stats['btts_pct']:.0%}")
        s6.metric("Over 2.5",   f"{league_stats['over_2_5_pct']:.0%}")
```

---

### 3. Current Standings
**Priority:** High | **Effort:** Low | **Impact:** High

Live La Liga table computed from the historical CSV (same approach as MLS standings).

```python
@st.cache_data(ttl=3600)
def compute_la_liga_standings(df: pd.DataFrame, season_start: str = "2025-08-01") -> pd.DataFrame:
    current = df[df["MatchDate"] >= season_start].copy()
    if current.empty:
        return pd.DataFrame()

    records = []
    for _, row in current.iterrows():
        home = row["HomeTeam"]
        away = row["AwayTeam"]
        hg = int(row.get("FullTimeHomeGoals", 0) or 0)
        ag = int(row.get("FullTimeAwayGoals", 0) or 0)
        result = row.get("FullTimeResult", "")

        hw = hd = hl = aw = ad = al = 0
        if result == "H":
            hw = 1; al = 1
        elif result == "D":
            hd = 1; ad = 1
        elif result == "A":
            hl = 1; aw = 1

        records.append({"Team": home, "GF": hg, "GA": ag, "W": hw, "D": hd, "L": hl})
        records.append({"Team": away, "GF": ag, "GA": hg, "W": aw, "D": ad, "L": al})

    mdf = pd.DataFrame(records)
    standings = mdf.groupby("Team").agg(
        Played=("GF", "count"),
        Win=("W", "sum"),
        Draw=("D", "sum"),
        Lose=("L", "sum"),
        GoalsFor=("GF", "sum"),
        GoalsAgainst=("GA", "sum"),
    ).reset_index()
    standings["GD"] = standings["GoalsFor"] - standings["GoalsAgainst"]
    standings["Points"] = standings["Win"] * 3 + standings["Draw"]
    standings = standings.sort_values(["Points", "GD", "GoalsFor"], ascending=False).reset_index(drop=True)
    standings["Rank"] = standings.index + 1

    def _form(team):
        rows = mdf[mdf["Team"] == team].tail(5)
        return "".join("W" if r["W"] else ("D" if r["D"] else "L") for _, r in rows.iterrows())
    standings["Form"] = standings["Team"].apply(_form)
    return standings[["Rank", "Team", "Played", "Win", "Draw", "Lose", "GoalsFor", "GoalsAgainst", "GD", "Points", "Form"]]
```

---

### 4. Upcoming Predictions Tab
**Priority:** High | **Effort:** Medium | **Impact:** Very High

Run the ensemble model against upcoming fixtures and display Home Win %, Draw %, Away Win %, Risk Score, Confidence %, and Betting Tip with color-coded risk rows.

```python
def calculate_prediction_risk(home_prob: float, draw_prob: float, away_prob: float):
    import numpy as np
    probs = np.clip([home_prob, draw_prob, away_prob], 1e-10, 1.0)
    entropy = -np.sum(probs * np.log(probs))
    confidence_score = 1 - (entropy / np.log(3))
    variance = np.sum((probs - 1 / 3) ** 2) / 3
    risk_score = min(100, max(0, (1 - confidence_score) * 50 + variance * 50))
    return risk_score, confidence_score

def risk_category(score: float) -> str:
    if score > 47: return "🚨 Critical"
    if score > 40: return "🔴 High"
    if score > 30: return "🟡 Moderate"
    return "🟢 Low"

def betting_recommendation(home_prob, draw_prob, away_prob, risk_score) -> str:
    max_prob = max(home_prob, draw_prob, away_prob)
    if max_prob >= 0.60 and risk_score <= 30:
        if home_prob == max_prob: return "💰 Bet Home Win"
        if draw_prob == max_prob: return "💰 Bet Draw"
        return "💰 Bet Away Win"
    if max_prob >= 0.50 and risk_score <= 50:
        if home_prob == max_prob: return "🤔 Consider Home"
        if draw_prob == max_prob: return "🤔 Consider Draw"
        return "🤔 Consider Away"
    return "❌ Avoid Betting"

def color_risk_rows(row):
    s = row["Risk Score"]
    if s <= 30:  return ["background-color:#d4edda;color:#155724"] * len(row)
    if s <= 40:  return ["background-color:#fff3cd;color:#856404"] * len(row)
    if s <= 47:  return ["background-color:#f8d7da;color:#721c24"] * len(row)
    return ["background-color:#f5c6cb;color:#721c24"] * len(row)
```

---

### 5. Statistics Tab
**Priority:** High | **Effort:** Medium | **Impact:** High

Four sub-sections:
- **xG Rankings** — FBref team xG For/Against table with attack/defense rank
- **Team Form** — Last 5 matches with W/D/L emoji indicators
- **Head-to-Head Analyzer** — Any two teams, last 10 H2H results
- **Copa del Rey Congestion** — Teams with recent Copa fixtures flagged

```python
# Team Form sub-section
st.markdown("### 📈 Recent Team Form (Last 5 Matches)")

all_teams = sorted(set(df["HomeTeam"].dropna()) | set(df["AwayTeam"].dropna()))
form_rows = []
for team in all_teams:
    home_m = df[df["HomeTeam"] == team][["MatchDate", "FullTimeResult"]].assign(
        won=lambda d: d["FullTimeResult"] == "H",
        draw=lambda d: d["FullTimeResult"] == "D",
    )
    away_m = df[df["AwayTeam"] == team][["MatchDate", "FullTimeResult"]].assign(
        won=lambda d: d["FullTimeResult"] == "A",
        draw=lambda d: d["FullTimeResult"] == "D",
    )
    all_m = pd.concat([home_m, away_m]).sort_values("MatchDate").tail(5)
    form_str = "".join("W" if r["won"] else ("D" if r["draw"] else "L") for _, r in all_m.iterrows())
    pts = sum(3 if c == "W" else (1 if c == "D" else 0) for c in form_str)

    def color_form(form_str: str) -> str:
        icons = {"W": "🟢", "D": "🟡", "L": "🔴"}
        return " ".join(icons.get(c, c) for c in form_str)

    form_rows.append({
        "Team": team,
        "Last 5": form_str,
        "Form": color_form(form_str),
        "Points": pts,
    })

form_df = pd.DataFrame(form_rows).sort_values("Points", ascending=False)
st.dataframe(form_df[["Team", "Form", "Points"]], hide_index=True)
```

---

### 6. Team Deep Dive Tab
**Priority:** Medium | **Effort:** Medium | **Impact:** Medium

Per-team KPIs: total matches, win rate, goals per game, xG per game (from FBref), home vs away split, Copa del Rey load, last 10 results.

```python
st.subheader("🔬 Team Deep Dive")
all_teams_dd = sorted(df["HomeTeam"].dropna().unique())
selected_team = st.selectbox("Select a team:", all_teams_dd, key="deep_dive_team")

home_m  = df[df["HomeTeam"] == selected_team]
away_m  = df[df["AwayTeam"] == selected_team]
total   = len(home_m) + len(away_m)

if total > 0:
    wins  = (home_m["FullTimeResult"] == "H").sum() + (away_m["FullTimeResult"] == "A").sum()
    draws = (home_m["FullTimeResult"] == "D").sum() + (away_m["FullTimeResult"] == "D").sum()
    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Total Matches", total)
    m2.metric("Wins", int(wins))
    m3.metric("Draws", int(draws))
    m4.metric("Win Rate", f"{wins / total:.1%}")
```

---

### 7. Prediction Performance Tracker
**Priority:** Medium | **Effort:** Medium | **Impact:** High

Log predictions for upcoming matches, then compare them against actual results once played. Display rolling accuracy over time.

```python
# track_predictions.py
import pandas as pd
from datetime import datetime
from os import path

LOG_FILE = "data_files/predictions_log.csv"

def log_prediction(date, home_team, away_team, pred_home, pred_draw, pred_away):
    row = {
        "PredictionDate": datetime.now().strftime("%Y-%m-%d"),
        "MatchDate": date,
        "HomeTeam": home_team,
        "AwayTeam": away_team,
        "PredHomeWin": pred_home,
        "PredDraw": pred_draw,
        "PredAwayWin": pred_away,
        "ActualResult": None,
        "Correct": None,
    }
    if path.exists(LOG_FILE):
        log_df = pd.read_csv(LOG_FILE)
        log_df = pd.concat([log_df, pd.DataFrame([row])], ignore_index=True)
    else:
        log_df = pd.DataFrame([row])
    log_df.to_csv(LOG_FILE, index=False)

def validate_predictions(results_df: pd.DataFrame):
    """Match logged predictions against actual results and mark Correct T/F."""
    if not path.exists(LOG_FILE):
        return None
    log_df = pd.read_csv(LOG_FILE)
    for i, row in log_df.iterrows():
        if pd.notna(row["Correct"]):
            continue
        match = results_df[
            (results_df["HomeTeam"] == row["HomeTeam"]) &
            (results_df["AwayTeam"] == row["AwayTeam"]) &
            (results_df["MatchDate"] == row["MatchDate"])
        ]
        if len(match) > 0:
            actual = match.iloc[0]["FullTimeResult"]
            log_df.at[i, "ActualResult"] = actual
            probs = {"H": row["PredHomeWin"], "D": row["PredDraw"], "A": row["PredAwayWin"]}
            predicted = max(probs, key=probs.get)
            log_df.at[i, "Correct"] = (predicted == actual)
    log_df.to_csv(LOG_FILE, index=False)
    return log_df
```

---

### 8. Copa del Rey Congestion Flag
**Priority:** Medium | **Effort:** Low | **Impact:** Medium

Flag teams that played a Copa del Rey match within the last 4 days. This is a La Liga-specific feature with no EPL/MLS equivalent.

```python
# In prepare_model_data.py
import pandas as pd

def add_copa_congestion_flag(df: pd.DataFrame, copa_fixtures: pd.DataFrame) -> pd.DataFrame:
    """
    Add binary flags: HomeCopaCongestion, AwayCopaCongestion.
    copa_fixtures must have: TeamName, MatchDate columns.
    """
    copa_fixtures["MatchDate"] = pd.to_datetime(copa_fixtures["MatchDate"])
    df["MatchDate"] = pd.to_datetime(df["MatchDate"])

    def days_since_copa(team: str, match_date: pd.Timestamp) -> int:
        recent = copa_fixtures[
            (copa_fixtures["TeamName"] == team) &
            (copa_fixtures["MatchDate"] < match_date)
        ]
        if recent.empty:
            return 999
        return (match_date - recent["MatchDate"].max()).days

    df["HomeCopaCongestion"] = df.apply(
        lambda r: 1 if days_since_copa(r["HomeTeam"], r["MatchDate"]) <= 4 else 0, axis=1
    )
    df["AwayCopaCongestion"] = df.apply(
        lambda r: 1 if days_since_copa(r["AwayTeam"], r["MatchDate"]) <= 4 else 0, axis=1
    )
    return df
```

---

### 9. Live Score Integration
**Priority:** Low | **Effort:** Medium | **Impact:** High

Fetch in-progress La Liga scores via ESPN's unofficial API.

```python
def fetch_live_la_liga_scores() -> pd.DataFrame:
    """Fetch live scores for in-progress La Liga matches (ESPN API)."""
    url = "https://site.api.espn.com/apis/site/v2/sports/soccer/esp.1/scoreboard"
    resp = requests.get(url, timeout=10)
    if resp.status_code != 200:
        return pd.DataFrame()

    live = []
    for event in resp.json().get("events", []):
        status = event.get("status", {}).get("type", {}).get("name", "")
        if status in ("STATUS_IN_PROGRESS", "STATUS_HALFTIME"):
            comp = event["competitions"][0]
            home = next(c for c in comp["competitors"] if c["homeAway"] == "home")
            away = next(c for c in comp["competitors"] if c["homeAway"] == "away")
            live.append({
                "HomeTeam": home["team"]["displayName"],
                "AwayTeam": away["team"]["displayName"],
                "HomeScore": home.get("score", "—"),
                "AwayScore": away.get("score", "—"),
                "Status": status,
                "Clock": event["status"].get("displayClock", ""),
            })
    return pd.DataFrame(live)

# In tab1
if st.toggle("🔴 Show Live Matches"):
    live_df = fetch_live_la_liga_scores()
    if len(live_df) > 0:
        st.dataframe(live_df, hide_index=True)
    else:
        st.info("No La Liga matches currently in progress.")
```

---

### 10. PDF Report Export
**Priority:** Low | **Effort:** Medium | **Impact:** Medium

Download a matchday predictions PDF.

```python
# generate_pdf_report.py
from fpdf import FPDF
import pandas as pd
from datetime import datetime

def generate_predictions_pdf(predictions_df: pd.DataFrame) -> bytes:
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Helvetica", "B", 16)
    pdf.cell(0, 10, "La Liga Linea — Matchday Predictions", ln=True, align="C")
    pdf.set_font("Helvetica", size=10)
    pdf.cell(0, 8, f"Generated: {datetime.now().strftime('%Y-%m-%d %I:%M %p ET')}", ln=True, align="C")
    pdf.ln(4)

    pdf.set_font("Helvetica", "B", 10)
    cols = ["HomeTeam", "AwayTeam", "Home Win %", "Draw %", "Away Win %", "Betting Tip"]
    col_widths = [45, 45, 22, 18, 22, 38]
    for col, w in zip(cols, col_widths):
        pdf.cell(w, 8, col, border=1, align="C")
    pdf.ln()

    pdf.set_font("Helvetica", size=9)
    for _, row in predictions_df.iterrows():
        for col, w in zip(cols, col_widths):
            pdf.cell(w, 7, str(row.get(col, "")), border=1, align="C")
        pdf.ln()

    return bytes(pdf.output())

# In Streamlit
@st.cache_data
def get_pdf(df):
    return generate_predictions_pdf(df)

pdf_bytes = get_pdf(display_df)
st.download_button(
    label="📄 Download PDF Report",
    data=pdf_bytes,
    file_name=f"la_liga_predictions_{datetime.now().strftime('%Y%m%d')}.pdf",
    mime="application/pdf",
)
```

---

## Implementation Timeline

**Phase 1 (Week 1-2):**
- ✅ Upcoming Fixtures Tab
- ✅ Season Stats Banner
- ✅ Current Standings
- ✅ Upcoming Predictions Tab

**Phase 2 (Week 3-4):**
- ✅ Statistics Tab (form + H2H)
- 🟡 Team Deep Dive Tab
- ✅ Coupe de France Congestion Flag

**Phase 3 (Month 2):**
- ✅ Prediction Performance Tracker
- ⚪ Live Score Integration
- ⚪ PDF Export

**Phase 4 (Month 3):**
- ✅ Markets Page (odds, EV)
- ✅ Best Bets Page
- 🟡 Mobile optimization
