# La Liga Linea 🇪🇸

**La Liga Linea** is an AI-powered prediction and betting analysis dashboard for Spain's *La Liga* (Primera División). It turns ten seasons of match data, live bookmaker odds, and advanced football metrics into clear match outcome probabilities, risk scores, and value-betting signals — all in a clean, interactive web app.

Part of the **Betting Oracle** suite alongside the MLS Predictor and Premier League Predictor.

---

## What It Does

Before every La Liga matchday, La Liga Linea:

- **Predicts** the probability of a Home Win, Draw, or Away Win for each upcoming fixture
- **Scores** every prediction by confidence and risk, flagging matches where the outcome is uncertain
- **Surfaces value bets** by comparing model probabilities against bookmaker implied odds — plays where your edge is ≥ 4% are highlighted in the Best Bets page
- **Shows you the table** — a live standings view built directly from historical results
- **Tracks its own record** — a rolling performance log validates accuracy over time

---

## Pages

### 🎯 Predictions
The main page. Every scheduled La Liga fixture appears here with:
- **Probability bars** for Home Win, Draw, and Away Win
- A **Risk Score** (Low / Moderate / High / Critical) based on the entropy of the probability distribution — a 40/35/25 split is a High Risk pick; a 72/18/10 split is Low Risk
- A **Betting Tip** distilled from the model's most confident call
- Color-coded rows so you can scan for value at a glance
- **Match commentary** that explains the reasoning behind each prediction in plain English

### 🗓️ Fixtures & Standings
- Live La Liga table with points, goal difference, form, and position
- Upcoming fixtures with matchday, kickoff time (Eastern), and weather forecast
- Season-level stat banner: home win rate, draw rate, BTTS, over 2.5 goals

### 📊 Statistics
- **xG Rankings** — team expected goals from FBref, updated nightly
- **Recent Form** — last-5-match form string and points for every team
- **Head-to-Head Analyzer** — select any two teams to see their last 10 meetings
- **Copa del Rey Congestion** — flags teams that played a Copa match within 4 days of their next La Liga fixture, a meaningful fatigue signal
- **Model Feature Importance** — see which inputs matter most to the XGBoost model

### 🔬 Team Deep Dive
Pick any team for a full breakdown:
- Season KPIs: goals for/against, xG, win/draw/loss split, clean sheets
- Home vs Away performance comparison
- Last 10 results table with outcomes color-coded green/amber/blue
- Form over time visualised as a cumulative points chart

### 📈 Markets
A full view of bookmaker odds and vig-removed implied probabilities for upcoming fixtures. Filter by bookmaker or team. Download the filtered table as CSV.

### 💰 Best Bets
Value plays only. A bet surfaces here when the model's probability for an outcome exceeds the market implied probability by at least 4 percentage points. Shows the edge, the decimal odds, and the bookmaker — sorted by edge descending.

### 📁 Raw Data
A filterable browser across all historical La Liga data — useful for manual research, sanity checks, or downloading a custom slice of results.

### 📈 Performance
The model's report card:
- Cumulative accuracy chart over all resolved predictions
- Precision, recall, and Brier score
- Backtest results: out-of-sample accuracy, flat-stake ROI, number of bets placed
- Full prediction log with correct/incorrect highlighted

---

## How the Model Works

The prediction engine is a **soft-voting ensemble** of four classifiers:

| Model | Weight | Strength |
|---|---|---|
| XGBoost | 2 | Captures non-linear feature interactions |
| Random Forest | 1.5 | Robust to noise, good calibration |
| Gradient Boosting | 1 | Adds sequential error correction |
| Logistic Regression | 0.5 | Stable baseline, interpretable |

Each model outputs probabilities for Home Win, Draw, and Away Win. The weighted average is the final prediction.

**Training data:** 10 seasons of SP1.csv from football-data.co.uk (approx. 3,800 matches).

**Features used** (all computed with a one-match lag to prevent data leakage):

| Feature | Window |
|---|---|
| Goals scored (home/away) | Last 5 |
| Goals conceded (home/away) | Last 5 |
| Win rate (home/away) | Last 10 |
| Momentum points (home/away) | Last 3 |
| Rest days since last match | — |
| Bookmaker implied probabilities | Current odds |
| Copa del Rey congestion flag | ≤ 4 days |

The model trains automatically on first launch and is cached. Delete `models/ensemble_model.pkl` to force a retrain.

---

## Themes

The app ships with a **Night** (dark navy) and **Day** (sky blue) theme. On first load, the theme is set automatically based on your browser's local time — day mode from 6 AM to 8 PM, night mode otherwise. You can override this at any time using the toggle in the sidebar.

---

## Setup (Developers)

```bash
git clone https://github.com/gmalbert/la-liga.git
cd la-liga
python -m venv venv
venv\Scripts\activate          # Windows
# source venv/bin/activate     # macOS / Linux
pip install -r requirements.txt
```

Create a `.env` file (never commit this):
```
FOOTBALL_DATA_KEY=your_football_data_org_key
ODDS_API_KEY=your_the_odds_api_key
```

Get your keys:
- [football-data.org](https://www.football-data.org/) — free tier covers La Liga (`PD`)
- [The Odds API](https://the-odds-api.com/) — free tier, sport key: `soccer_spain_la_liga`

```bash
# Fetch data
python fetch_historical_csvs.py     # 10 seasons of La Liga results
python fetch_upcoming_fixtures.py   # upcoming fixtures
python fetch_fbref_xg.py            # team xG from FBref
python fetch_odds.py                # bookmaker odds

# Launch
streamlit run predictions.py
```

The model trains on first load. All data refreshes nightly via GitHub Actions.

See [`docs/README.md`](docs/README.md) for the full implementation roadmap.
