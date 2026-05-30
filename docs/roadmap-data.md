# Data Enhancement Roadmap — Ligue Odds

## Status
- ✅ Core Ligue 1 data pipelines are implemented.
- 🟡 Partial/adapted: true FBref/Understat scraping has been replaced by a shot-on-target xG proxy; football-data.org is used for fixtures/results, while standings are computed locally.
- ⚪ Outstanding: injury data, KNN imputation, and historical weather features in model training.
- Reviewed: 2026-05-28

## Current Implementation Status

| # | Data Addition | Status |
|---|---|---|
| 1 | football-data.org core pipeline | 🟡 Implemented for upcoming Ligue 1 fixtures/results with `FL1`; standings are currently computed from local historical CSV data |
| 2 | football-data.co.uk historical CSVs | ✅ Implemented for Ligue 1 `FR1.csv` seasons in `fetch_historical_csvs.py` |
| 3 | FBref xG scraper | 🟡 Implemented as `fetch_fbref_xg.py`, but currently generates shot-on-target xG proxy files instead of scraping FBref |
| 4 | Betting odds | ✅ Implemented in `fetch_odds.py` with vig-removed implied probabilities |
| 5 | Weather data | 🟡 Implemented for upcoming fixture forecasts in `fetch_weather_data.py`; historical weather model features remain outstanding |
| 6 | Cup fixtures | ✅ Adapted to Coupe de France via ESPN in `fetch_copa_fixtures.py` |
| 7 | Implied probability features | ✅ Implemented in `prepare_model_data.py` |
| 8 | Injury data | ⚪ Not implemented |
| 9 | Missing data KNN imputation | ⚪ Not implemented |
| 10 | Team name normalization | ✅ Implemented in `team_name_mapping.py` |

## Current Data Sources (Starting Point)
- Historical match results: football-data.co.uk (FR1, 2015–2025)
- Upcoming fixtures: football-data.org API v4 (`FL1`)
- Basic match stats: goals, shots, shots on target, corners, fouls, cards

---

## Priority Data Additions

### 1. football-data.org API — Core Pipeline
**Priority:** High | **Impact:** Very High  
**Cost:** Free tier (10 req/min, covers PD)  
**La Liga competition code:** `PD` (Primera División)

```python
# fetch_fd_data.py
import requests
import pandas as pd
from pathlib import Path

API_KEY  = "your_football_data_org_key"   # store in .env, never commit
BASE_URL = "https://api.football-data.org/v4"
HEADERS  = {"X-Auth-Token": API_KEY}

def fetch_pd_matches(season: int = 2024) -> pd.DataFrame:
    """
    Fetch all La Liga matches for a given season.
    season=2024 → 2024-25 season.
    """
    resp = requests.get(
        f"{BASE_URL}/competitions/PD/matches",
        headers=HEADERS,
        params={"season": season},
        timeout=15,
    )
    resp.raise_for_status()
    matches = resp.json().get("matches", [])

    rows = []
    for m in matches:
        rows.append({
            "MatchDate":          m["utcDate"][:10],
            "Matchday":           m.get("matchday"),
            "HomeTeam":           m["homeTeam"]["name"],
            "AwayTeam":           m["awayTeam"]["name"],
            "FullTimeHomeGoals":  (m["score"]["fullTime"].get("home") or ""),
            "FullTimeAwayGoals":  (m["score"]["fullTime"].get("away") or ""),
            "FullTimeResult":     _result(m),
            "HalfTimeHomeGoals":  (m["score"]["halfTime"].get("home") or ""),
            "HalfTimeAwayGoals":  (m["score"]["halfTime"].get("away") or ""),
            "Status":             m["status"],
        })
    return pd.DataFrame(rows)


def _result(match: dict) -> str:
    score = match["score"]["fullTime"]
    h, a = score.get("home"), score.get("away")
    if h is None or a is None:
        return ""
    if h > a: return "H"
    if h < a: return "A"
    return "D"


def fetch_pd_standings(season: int = 2024) -> pd.DataFrame:
    resp = requests.get(
        f"{BASE_URL}/competitions/PD/standings",
        headers=HEADERS,
        params={"season": season},
        timeout=15,
    )
    resp.raise_for_status()
    standings = resp.json()["standings"][0]["table"]
    return pd.DataFrame([{
        "Position": row["position"],
        "Team":     row["team"]["name"],
        "Played":   row["playedGames"],
        "Won":      row["won"],
        "Draw":     row["draw"],
        "Lost":     row["lost"],
        "GF":       row["goalsFor"],
        "GA":       row["goalsAgainst"],
        "GD":       row["goalDifference"],
        "Points":   row["points"],
    } for row in standings])


if __name__ == "__main__":
    Path("data_files/raw").mkdir(parents=True, exist_ok=True)
    df = fetch_pd_matches()
    df.to_csv("data_files/raw/pd_matches_2024.csv", index=False)
    print(f"Fetched {len(df)} matches.")
```

---

### 2. football-data.co.uk — Historical CSV Bulk Download
**Priority:** High | **Impact:** Very High  
**Cost:** Free  
**URL pattern:** `https://www.football-data.co.uk/mmz4281/{YYMM}/SP1.csv`  
**Column reference:** https://www.football-data.co.uk/notes.txt

```python
# fetch_historical_csvs.py
import requests
import pandas as pd
from pathlib import Path
import io

SEASONS = {
    "1516": "2015-16", "1617": "2016-17", "1718": "2017-18",
    "1819": "2018-19", "1920": "2019-20", "2021": "2020-21",
    "2122": "2021-22", "2223": "2022-23", "2324": "2023-24",
    "2425": "2024-25",
}

COLUMN_MAP = {
    "Date":   "MatchDate",
    "HomeTeam": "HomeTeam",
    "AwayTeam": "AwayTeam",
    "FTHG":   "FullTimeHomeGoals",
    "FTAG":   "FullTimeAwayGoals",
    "FTR":    "FullTimeResult",
    "HTHG":   "HalfTimeHomeGoals",
    "HTAG":   "HalfTimeAwayGoals",
    "HTR":    "HalfTimeResult",
    "Referee":"Referee",
    "HS":     "HomeShots",
    "AS":     "AwayShots",
    "HST":    "HomeShotsOnTarget",
    "AST":    "AwayShotsOnTarget",
    "HF":     "HomeFouls",
    "AF":     "AwayFouls",
    "HC":     "HomeCorners",
    "AC":     "AwayCorners",
    "HY":     "HomeYellowCards",
    "AY":     "AwayYellowCards",
    "HR":     "HomeRedCards",
    "AR":     "AwayRedCards",
    # Betting odds
    "B365H":  "Bet365_HomeWinOdds",
    "B365D":  "Bet365_DrawOdds",
    "B365A":  "Bet365_AwayWinOdds",
    "BWH":    "BW_HomeWinOdds",
    "BWD":    "BW_DrawOdds",
    "BWA":    "BW_AwayWinOdds",
    "PSH":    "Pinnacle_HomeWinOdds",
    "PSD":    "Pinnacle_DrawOdds",
    "PSA":    "Pinnacle_AwayWinOdds",
}

def download_season(season_code: str, season_label: str) -> pd.DataFrame:
    url = f"https://www.football-data.co.uk/mmz4281/{season_code}/SP1.csv"
    try:
        resp = requests.get(url, timeout=15)
        resp.raise_for_status()
        df = pd.read_csv(io.StringIO(resp.text), encoding="latin-1", on_bad_lines="skip")
        df = df.rename(columns={k: v for k, v in COLUMN_MAP.items() if k in df.columns})
        df["Season"] = season_label
        df["MatchDate"] = pd.to_datetime(df["MatchDate"], dayfirst=True, errors="coerce")
        return df
    except Exception as e:
        print(f"  ✗ {season_label}: {e}")
        return pd.DataFrame()

def build_historical_dataset() -> pd.DataFrame:
    Path("data_files/raw").mkdir(parents=True, exist_ok=True)
    frames = []
    for code, label in SEASONS.items():
        print(f"Downloading {label}...")
        df = download_season(code, label)
        if not df.empty:
            df.to_csv(f"data_files/raw/SP1_{code}.csv", index=False)
            frames.append(df)
    combined = pd.concat(frames, ignore_index=True)
    combined.sort_values("MatchDate", inplace=True)
    combined.to_csv("data_files/combined_historical_data.csv", index=False)
    print(f"\n✓ Combined: {len(combined)} matches across {len(frames)} seasons.")
    return combined

if __name__ == "__main__":
    build_historical_dataset()
```

---

### 3. FBref xG Scraper — Advanced Metrics
**Priority:** High | **Impact:** Very High  
**Cost:** Free (scraping)  
**URL:** `https://fbref.com/en/comps/12/La-Liga-Stats` (La Liga = comp 12 on FBref)

```python
# fetch_fbref_xg.py
import requests
import pandas as pd
from bs4 import BeautifulSoup
import time

FBREF_LA_LIGA_URL = "https://fbref.com/en/comps/12/La-Liga-Stats"
HEADERS = {"User-Agent": "Mozilla/5.0 (compatible; research-bot/1.0)"}

def scrape_fbref_team_xg(season_url: str = FBREF_LA_LIGA_URL) -> pd.DataFrame:
    """
    Scrape team-level xG, xGA, possession, and progressive stats from FBref.
    Returns DataFrame with one row per team.
    """
    time.sleep(4)  # Be a polite scraper
    resp = requests.get(season_url, headers=HEADERS, timeout=20)
    resp.raise_for_status()

    soup = BeautifulSoup(resp.text, "html.parser")

    # FBref table id for La Liga squad stats
    table = soup.find("table", {"id": "stats_squads_shooting_for"})
    if table is None:
        # Fall back to first stats table
        table = soup.find("table", class_="stats_table")
    if table is None:
        print("Could not find FBref stats table.")
        return pd.DataFrame()

    df = pd.read_html(str(table))[0]

    # Flatten multi-level columns
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = ["_".join(c).strip("_") for c in df.columns.values]

    # Keep and rename relevant columns
    col_map = {
        "Squad":                          "Team",
        "Expected_xG":                    "xG",
        "Expected_xGA":                   "xGA",
        "Expected_xGD":                   "xGD",
        "Expected_xGD/90":                "xGD_per90",
        "Poss":                           "Possession",
        "Performance_Gls":                "Goals",
        "Performance_GA":                 "GoalsAgainst",
        "Performance_W":                  "Wins",
        "Performance_D":                  "Draws",
        "Performance_L":                  "Losses",
        "Playing Time_MP":                "MatchesPlayed",
    }
    df = df.rename(columns={k: v for k, v in col_map.items() if k in df.columns})
    df = df[df["Team"].notna() & (df["Team"] != "Team")].reset_index(drop=True)

    numeric_cols = ["xG", "xGA", "xGD", "xGD_per90", "Possession", "Goals", "GoalsAgainst",
                    "Wins", "Draws", "Losses", "MatchesPlayed"]
    for col in numeric_cols:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")

    df.to_csv("data_files/raw/fbref_team_xg.csv", index=False)
    print(f"Scraped xG data for {len(df)} teams.")
    return df


def scrape_fbref_match_xg(season_url: str = FBREF_LA_LIGA_URL) -> pd.DataFrame:
    """
    Scrape match-by-match xG from FBref scores & fixtures page.
    URL: https://fbref.com/en/comps/12/schedule/La-Liga-Scores-and-Fixtures
    """
    scores_url = season_url.replace("Stats", "Scores-and-Fixtures").replace(
        "La-Liga-Stats", "schedule/La-Liga-Scores-and-Fixtures"
    )
    time.sleep(4)
    resp = requests.get(scores_url, headers=HEADERS, timeout=20)
    resp.raise_for_status()

    soup = BeautifulSoup(resp.text, "html.parser")
    table = soup.find("table", {"id": "sched_all"})
    if table is None:
        return pd.DataFrame()

    df = pd.read_html(str(table))[0]
    df.columns = [str(c) for c in df.columns]
    df = df[df["Date"].notna() & (df["Date"] != "Date")].copy()

    col_map = {
        "Date": "MatchDate", "Home": "HomeTeam", "Away": "AwayTeam",
        "xG": "Home_xG", "xG.1": "Away_xG", "Score": "Score",
        "Wk": "Matchday",
    }
    df = df.rename(columns={k: v for k, v in col_map.items() if k in df.columns})
    df["MatchDate"] = pd.to_datetime(df.get("MatchDate", ""), errors="coerce")

    df.to_csv("data_files/raw/fbref_match_xg.csv", index=False)
    print(f"Scraped {len(df)} match xG records.")
    return df


if __name__ == "__main__":
    scrape_fbref_team_xg()
    scrape_fbref_match_xg()
```

---

### 4. Betting Odds — The Odds API
**Priority:** High | **Impact:** High  
**Cost:** Free tier (500 req/month)  
**Docs:** https://the-odds-api.com/

```python
# fetch_odds.py
import requests
import pandas as pd
from pathlib import Path

ODDS_API_KEY = "your_odds_api_key"   # store in .env
ODDS_API_BASE = "https://api.the-odds-api.com/v4"

SPORT_KEY = "soccer_spain_la_liga"

def fetch_upcoming_odds() -> pd.DataFrame:
    """Fetch upcoming La Liga match odds (1X2 moneyline)."""
    resp = requests.get(
        f"{ODDS_API_BASE}/sports/{SPORT_KEY}/odds",
        params={
            "apiKey": ODDS_API_KEY,
            "regions": "us",
            "markets": "h2h",        # 1X2
            "oddsFormat": "decimal",
            "bookmakers": "draftkings,betmgm,pinnacle",
        },
        timeout=15,
    )
    resp.raise_for_status()
    games = resp.json()

    rows = []
    for game in games:
        home = game["home_team"]
        away = game["away_team"]
        date = game["commence_time"][:10]

        for bm in game.get("bookmakers", []):
            for market in bm.get("markets", []):
                if market["key"] != "h2h":
                    continue
                prices = {o["name"]: o["price"] for o in market["outcomes"]}
                rows.append({
                    "Date":         date,
                    "HomeTeam":     home,
                    "AwayTeam":     away,
                    "Bookmaker":    bm["key"],
                    "HomeWinOdds":  prices.get(home),
                    "DrawOdds":     prices.get("Draw"),
                    "AwayWinOdds":  prices.get(away),
                })

    df = pd.DataFrame(rows)
    Path("data_files/raw").mkdir(parents=True, exist_ok=True)
    df.to_csv("data_files/raw/odds.csv", index=False)
    print(f"Fetched odds for {len(games)} games.")
    return df


def extract_implied_probabilities(df: pd.DataFrame) -> pd.DataFrame:
    """Convert decimal odds to vig-removed implied probabilities."""
    df = df.copy()
    df["RawHome"] = 1 / df["HomeWinOdds"]
    df["RawDraw"] = 1 / df["DrawOdds"]
    df["RawAway"] = 1 / df["AwayWinOdds"]
    total = df["RawHome"] + df["RawDraw"] + df["RawAway"]
    df["ImpliedProb_HomeWin"] = (df["RawHome"] / total).round(4)
    df["ImpliedProb_Draw"]    = (df["RawDraw"]  / total).round(4)
    df["ImpliedProb_AwayWin"] = (df["RawAway"]  / total).round(4)
    df["BookmakerMargin"]     = ((total - 1) * 100).round(2)
    return df.drop(columns=["RawHome", "RawDraw", "RawAway"])


if __name__ == "__main__":
    df_odds = fetch_upcoming_odds()
    df_probs = extract_implied_probabilities(df_odds)
    print(df_probs.head())
```

---

### 5. Weather Data — Open-Meteo (Free, No API Key)
**Priority:** Medium | **Impact:** Medium  
**Cost:** Free — no API key required

```python
# fetch_weather_data.py
import requests
import pandas as pd
from datetime import datetime

# La Liga stadium GPS coordinates
LA_LIGA_STADIUMS = {
    "Real Madrid CF":             {"lat": 40.4531, "lon": -3.6883, "stadium": "Santiago Bernabéu"},
    "FC Barcelona":               {"lat": 41.3809, "lon":  2.1228, "stadium": "Camp Nou / Estadi Olímpic"},
    "Atletico de Madrid":         {"lat": 40.4360, "lon": -3.5995, "stadium": "Metropolitano"},
    "Sevilla FC":                 {"lat": 37.3840, "lon": -5.9705, "stadium": "Estadio Ramón Sánchez-Pizjuán"},
    "Real Betis Balompié":        {"lat": 37.3563, "lon": -5.9810, "stadium": "Estadio Benito Villamarín"},
    "Athletic Club":              {"lat": 43.2641, "lon": -2.9494, "stadium": "San Mamés"},
    "Real Sociedad":              {"lat": 43.3015, "lon": -1.9738, "stadium": "Reale Arena"},
    "Villarreal CF":              {"lat": 39.9440, "lon": -0.1035, "stadium": "Estadio de la Cerámica"},
    "Valencia CF":                {"lat": 39.4747, "lon": -0.3583, "stadium": "Estadio de Mestalla"},
    "Getafe CF":                  {"lat": 40.3256, "lon": -3.7167, "stadium": "Estadio Coliseum Alfonso Pérez"},
    "RC Celta de Vigo":           {"lat": 42.2121, "lon": -8.7393, "stadium": "Abanca-Balaídos"},
    "Rayo Vallecano":             {"lat": 40.3920, "lon": -3.6564, "stadium": "Campo de Fútbol de Vallecas"},
    "Osasuna":                    {"lat": 42.7969, "lon": -1.6369, "stadium": "El Sadar"},
    "Girona FC":                  {"lat": 41.9807, "lon":  2.8152, "stadium": "Estadi Montilivi"},
    "UD Las Palmas":              {"lat": 28.1002, "lon": -15.4560, "stadium": "Estadio Gran Canaria"},
    "Real Valladolid CF":         {"lat": 41.6517, "lon": -4.7286, "stadium": "Estadio José Zorrilla"},
    "Deportivo Alavés":           {"lat": 42.8474, "lon": -2.6780, "stadium": "Estadio de Mendizorroza"},
    "CD Leganés":                 {"lat": 40.3295, "lon": -3.7630, "stadium": "Estadio Municipal de Butarque"},
    "RCD Espanyol":               {"lat": 41.3476, "lon":  2.0758, "stadium": "RCDE Stadium"},
    "Real Mallorca":              {"lat": 39.5907, "lon":  2.6333, "stadium": "Estadio de Son Moix"},
}

def fetch_match_weather(team: str, match_date: str) -> dict:
    """
    Fetch historical weather for a match using Open-Meteo Archive API.
    match_date: 'YYYY-MM-DD'
    """
    coords = LA_LIGA_STADIUMS.get(team)
    if not coords:
        return {}

    url = "https://archive-api.open-meteo.com/v1/archive"
    params = {
        "latitude":   coords["lat"],
        "longitude":  coords["lon"],
        "start_date": match_date,
        "end_date":   match_date,
        "daily":      "temperature_2m_max,precipitation_sum,windspeed_10m_max",
        "timezone":   "Europe/Madrid",
    }
    try:
        resp = requests.get(url, params=params, timeout=10)
        resp.raise_for_status()
        data = resp.json().get("daily", {})
        temp  = (data.get("temperature_2m_max") or [None])[0]
        rain  = (data.get("precipitation_sum") or [None])[0]
        wind  = (data.get("windspeed_10m_max") or [None])[0]
        return {
            "Temperature":   temp,
            "Precipitation": rain,
            "WindSpeed":     wind,
            "WeatherImpact": _categorize(temp, rain, wind),
        }
    except Exception:
        return {}


def _categorize(temp, rain, wind) -> str:
    if rain and rain > 5:    return "Heavy Rain"
    if wind and wind > 50:   return "Windy"
    if temp and temp < 5:    return "Cold"
    if temp and temp > 30:   return "Hot"
    return "Normal"


def add_weather_features(df: pd.DataFrame) -> pd.DataFrame:
    """Enrich historical DataFrame with weather data (with caching)."""
    weather_rows = []
    for _, row in df.iterrows():
        w = fetch_match_weather(row["HomeTeam"], str(row["MatchDate"])[:10])
        weather_rows.append(w)
    weather_df = pd.DataFrame(weather_rows, index=df.index)
    return pd.concat([df, weather_df], axis=1)
```

---

### 6. Copa del Rey Fixtures
**Priority:** Medium | **Impact:** Medium  
**Cost:** Free (football-data.org)  
**Competition code:** `CDR` (Copa del Rey)

```python
# fetch_copa_fixtures.py
import requests
import pandas as pd

API_KEY  = "your_football_data_org_key"
BASE_URL = "https://api.football-data.org/v4"
HEADERS  = {"X-Auth-Token": API_KEY}

def fetch_copa_del_rey_fixtures(season: int = 2024) -> pd.DataFrame:
    """Fetch Copa del Rey fixtures to compute congestion flags."""
    resp = requests.get(
        f"{BASE_URL}/competitions/CDR/matches",
        headers=HEADERS,
        params={"season": season},
        timeout=15,
    )
    resp.raise_for_status()
    matches = resp.json().get("matches", [])

    rows = []
    for m in matches:
        rows.append({
            "MatchDate": m["utcDate"][:10],
            "HomeTeam":  m["homeTeam"]["name"],
            "AwayTeam":  m["awayTeam"]["name"],
            "Competition": "Copa del Rey",
        })

    df = pd.DataFrame(rows)
    # Normalize to long format: one row per team per match
    home_df = df[["MatchDate", "HomeTeam"]].rename(columns={"HomeTeam": "TeamName"})
    away_df = df[["MatchDate", "AwayTeam"]].rename(columns={"AwayTeam": "TeamName"})
    copa_long = pd.concat([home_df, away_df]).drop_duplicates().reset_index(drop=True)
    copa_long["MatchDate"] = pd.to_datetime(copa_long["MatchDate"])
    copa_long.to_csv("data_files/raw/copa_fixtures.csv", index=False)
    return copa_long
```

---

### 7. Implied Probability Features from Historical Odds
**Priority:** High | **Impact:** High  
**Source:** football-data.co.uk CSVs include Bet365, Pinnacle, BetWin, etc.

```python
# In prepare_model_data.py

def extract_betting_features(df: pd.DataFrame) -> pd.DataFrame:
    """
    Derive implied probability and market efficiency features from historical odds.
    Closing-line implied probs are among the strongest predictors available.
    """
    df = df.copy()

    # Use Pinnacle as primary (sharpest book); fall back to Bet365
    home_odds_col = next((c for c in ["Pinnacle_HomeWinOdds", "Bet365_HomeWinOdds"] if c in df.columns), None)
    draw_odds_col = next((c for c in ["Pinnacle_DrawOdds",    "Bet365_DrawOdds"]    if c in df.columns), None)
    away_odds_col = next((c for c in ["Pinnacle_AwayWinOdds", "Bet365_AwayWinOdds"] if c in df.columns), None)

    if not all([home_odds_col, draw_odds_col, away_odds_col]):
        return df

    df["RawProb_H"] = 1 / df[home_odds_col]
    df["RawProb_D"] = 1 / df[draw_odds_col]
    df["RawProb_A"] = 1 / df[away_odds_col]
    margin = df["RawProb_H"] + df["RawProb_D"] + df["RawProb_A"]

    df["ImpliedProb_HomeWin"] = (df["RawProb_H"] / margin).round(4)
    df["ImpliedProb_Draw"]    = (df["RawProb_D"] / margin).round(4)
    df["ImpliedProb_AwayWin"] = (df["RawProb_A"] / margin).round(4)
    df["BookmakerMargin"]     = ((margin - 1) * 100).round(2)

    # Odds movement: compare Bet365 vs Pinnacle if both available
    if "Bet365_HomeWinOdds" in df.columns and "Pinnacle_HomeWinOdds" in df.columns:
        df["OddsMovement_Home"] = (df["Bet365_HomeWinOdds"] - df["Pinnacle_HomeWinOdds"]).round(3)
        df["OddsMovement_Away"] = (df["Bet365_AwayWinOdds"] - df["Pinnacle_AwayWinOdds"]).round(3)

    df.drop(columns=["RawProb_H", "RawProb_D", "RawProb_A"], inplace=True)
    return df
```

---

### 8. Injury Data
**Priority:** Medium | **Impact:** High  
**Source:** Transfermarkt / football-injury-news.com (scraping) or API-Football

```python
# scrape_injuries.py
import requests
from bs4 import BeautifulSoup
import pandas as pd

def scrape_la_liga_injuries() -> pd.DataFrame:
    """
    Scrape current La Liga injury list from football-injury-news.com.
    Returns DataFrame with Team, Player, InjuryType, ExpectedReturn.
    """
    url = "https://www.footballinjurynews.com/la-liga"
    headers = {"User-Agent": "Mozilla/5.0 (compatible; research-bot/1.0)"}
    try:
        resp = requests.get(url, headers=headers, timeout=15)
        resp.raise_for_status()
    except Exception as e:
        print(f"Injury scrape failed: {e}")
        return pd.DataFrame()

    soup = BeautifulSoup(resp.text, "html.parser")
    rows = []
    for card in soup.select(".team-injuries"):
        team = card.select_one(".team-name")
        team_name = team.text.strip() if team else "Unknown"
        for player in card.select(".player-injury"):
            rows.append({
                "Team":    team_name,
                "Player":  player.select_one(".player-name").text.strip() if player.select_one(".player-name") else "",
                "Injury":  player.select_one(".injury-type").text.strip() if player.select_one(".injury-type") else "",
                "Return":  player.select_one(".return-date").text.strip() if player.select_one(".return-date") else "",
            })

    return pd.DataFrame(rows)


def create_injury_features(df: pd.DataFrame, injury_df: pd.DataFrame) -> pd.DataFrame:
    """Add HomeInjuryCount, AwayInjuryCount, InjuryAdvantage to match DataFrame."""
    if injury_df.empty:
        df["HomeInjuryCount"] = 0
        df["AwayInjuryCount"] = 0
        df["InjuryAdvantage"] = 0
        return df

    counts = injury_df.groupby("Team").size().to_dict()
    df["HomeInjuryCount"] = df["HomeTeam"].map(counts).fillna(0).astype(int)
    df["AwayInjuryCount"] = df["AwayTeam"].map(counts).fillna(0).astype(int)
    df["InjuryAdvantage"] = df["AwayInjuryCount"] - df["HomeInjuryCount"]
    return df
```

---

### 9. Missing Data Handling — KNN Imputation
**Priority:** Medium | **Impact:** Medium

```python
# In prepare_model_data.py
from sklearn.impute import KNNImputer
import numpy as np

def smart_imputation(df: pd.DataFrame) -> pd.DataFrame:
    """KNN imputation for all numeric columns to minimize missing values."""
    numeric_cols = df.select_dtypes(include=[np.number]).columns.tolist()
    cols_to_impute = [c for c in numeric_cols if df[c].notna().sum() > 0]

    if cols_to_impute:
        imputer = KNNImputer(n_neighbors=5)
        df[cols_to_impute] = imputer.fit_transform(df[cols_to_impute])

    # Any remaining all-null columns: fill with 0
    for col in numeric_cols:
        if df[col].isnull().all():
            df[col] = df[col].fillna(0)

    return df
```

---

## Data Quality

### Team Name Normalization
football-data.co.uk, football-data.org, FBref, and ESPN all use different spellings. A mapping table is required.

```python
# team_name_mapping.py

LA_LIGA_TEAM_MAP = {
    # football-data.co.uk → canonical
    "Barcelona":            "FC Barcelona",
    "Ath Madrid":           "Atletico de Madrid",
    "Ath Bilbao":           "Athletic Club",
    "Betis":                "Real Betis Balompié",
    "Sociedad":             "Real Sociedad",
    "Espanol":              "RCD Espanyol",
    "Villarreal":           "Villarreal CF",
    "Celta":                "RC Celta de Vigo",
    "Getafe":               "Getafe CF",
    "Osasuna":              "Osasuna",
    "Valencia":             "Valencia CF",
    "Vallecano":            "Rayo Vallecano",
    "Girona":               "Girona FC",
    "Las Palmas":           "UD Las Palmas",
    "Valladolid":           "Real Valladolid CF",
    "Alaves":               "Deportivo Alavés",
    "Leganes":              "CD Leganés",
    "Mallorca":             "Real Mallorca",
    "Sevilla":              "Sevilla FC",
    "Real Madrid":          "Real Madrid CF",
    # FBref variants
    "Atlético Madrid":      "Atletico de Madrid",
    "Atlético de Madrid":   "Atletico de Madrid",
    "Espanyol":             "RCD Espanyol",
    "Celta Vigo":           "RC Celta de Vigo",
}

def normalize_team_name(name: str) -> str:
    if not isinstance(name, str):
        return name
    return LA_LIGA_TEAM_MAP.get(name.strip(), name.strip())
```

---

## Implementation Priority

**Phase 1 (Week 1):**
1. ✅ `fetch_historical_csvs.py` — build 10-season Ligue 1 dataset
2. ✅ `team_name_mapping.py` — normalize all team names
3. ✅ `prepare_model_data.py` — core feature engineering

**Phase 2 (Week 2):**
4. 🟡 `fetch_fd_data.py` — not present; upcoming fixtures/results are handled by `fetch_upcoming_fixtures.py`
5. ✅ `extract_betting_features()` — implied probabilities from historical odds are implemented in `prepare_model_data.py`
6. ✅ `fetch_upcoming_fixtures.py` — upcoming `FL1` fixtures

**Phase 3 (Month 1):**
7. 🟡 `fetch_fbref_xg.py` — xG proxy implemented; real FBref/Understat xG still outstanding
8. ✅ `fetch_copa_fixtures.py` — Coupe de France congestion flag
9. ⚪ `smart_imputation()` — KNN imputation for missing values

**Phase 4 (Month 2):**
10. ✅ `fetch_odds.py` — live The Odds API integration
11. ⚪ `scrape_injuries.py` — injury counts
12. 🟡 `fetch_weather_data.py` — upcoming weather forecasts implemented; training features outstanding
