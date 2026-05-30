<a id="top"></a>

<p align="center">
  <img src="data_files/logo.png" alt="Ligue Odds logo" width="220">
</p>

# Ligue Odds

*Ligue Odds* is an AI-powered prediction and betting analysis dashboard for France's **Ligue 1**. It turns ten seasons of match data, bookmaker odds, and football metrics into match probabilities, risk scores, standings, and value-betting signals in a Streamlit app.

Part of the **Betting Oracle** suite alongside the MLS Predictor and Premier League Predictor.

## Table Of Contents

- [What It Does](#what-it-does)
- [Pages](#pages)
- [How The Model Works](#how-the-model-works)
- [Nightly Data Pipeline](#nightly-data-pipeline)
- [Themes](#themes)
- [Local Setup](#local-setup)
- [Docs](#docs)

## What It Does

Before every Ligue 1 matchday, Ligue Odds:

- **Predicts** home win, draw, and away win probabilities for each scheduled fixture.
- **Scores risk** using confidence and probability spread.
- **Surfaces value bets** by comparing model probabilities against market implied odds.
- **Shows standings** built from historical Ligue 1 results.
- **Tracks performance** through resolved prediction logs and backtests.

[Back to top](#top)

## Pages

### Predictions

The main page shows upcoming match predictions when fixtures are available. During off-season or empty slates, it shows a friendlier overview with current slate status, standings, top model signals, and navigation to key areas.

### Fixtures & Standings

Live standings, upcoming fixtures, kickoff times in Eastern Time, weather, and season-level stats.

### Statistics

xG proxy rankings, recent form, head-to-head analysis, Coupe de France congestion flags, and model feature importance.

### Team Deep Dive

Team KPIs, home/away splits, and recent results for any selected club.

### Markets

Bookmaker odds and vig-removed implied probabilities for upcoming fixtures.

### Best Bets

Value plays where the model probability exceeds the market implied probability by the configured edge threshold.

### Raw Data

A filterable browser for historical Ligue 1 match data, with a data dictionary and CSV download.

### Performance

Prediction accuracy, resolved prediction logs, and historical backtest results.

[Back to top](#top)

## How The Model Works

The prediction engine starts with a **soft-voting ensemble**:

| Model | Weight | Strength |
|---|---:|---|
| XGBoost | 2.0 | Captures non-linear feature interactions |
| Random Forest | 1.5 | Robust to noisy tabular data |
| Gradient Boosting | 1.0 | Adds sequential error correction |
| Logistic Regression | 0.5 | Stable interpretable baseline |

Each model outputs probabilities for Home Win, Draw, and Away Win. Those probabilities are evaluated against the bookmaker-implied market baseline, then blended with market probabilities when validation log loss improves. This prevents the model from inventing artificial edges when the market is already stronger.

**Training data:** Ligue 1 `FR1.csv` data from football-data.co.uk, currently 2015-16 through 2025-26 when available.

| Feature | Window |
|---|---|
| Goals scored and conceded | Last 5 |
| Shots and shots on target | Last 5 |
| Win rate | Last 10 |
| Momentum points | Last 3 |
| Rest days since last match | Previous fixture |
| Home/away venue splits | Last 5-10 |
| Elo team strength | Pre-match |
| Bookmaker implied probabilities | Current market |
| Coupe de France congestion flag | Nearby cup fixture |

Reported accuracy is exact 3-way classification accuracy: the top predicted result must match Home Win, Draw, or Away Win. The headline validation uses the latest full season as the holdout. The app also tracks log loss, Brier score, market baseline deltas, calibration error, ROI, closing line value, draw recall, macro F1, ROC AUC, majority baseline accuracy, market baseline accuracy, and walk-forward season summaries.

[Back to top](#top)

## Nightly Data Pipeline

Models, predictions, and app-cache artifacts are generated nightly so users do not wait for model training or common table calculations when opening the app.

The nightly flow:

- Fetches historical Ligue 1 data, upcoming fixtures, odds, weather, xG proxy data, and Coupe de France fixtures.
- Stores append-only market odds snapshots for movement, consensus, totals, BTTS, and future CLV features.
- Pulls API-Football enrichment for match statistics/xG when available, injuries, lineups, and squad lists with a 100-request/day quota guard.
- Prepares model-ready features.
- Builds an additive enriched feature store at `data_files/model_features/enriched_match_features.csv`.
- Trains ensemble, Poisson, and neural-network models.
- Runs the historical backtest.
- Pre-generates prediction logs.
- Builds app-cache files for standings, league stats, team form, and feature importance.

Current note: live odds can come from `odds-api.io` or The Odds API. The default local setup prefers `odds-api.io` when `ODDS_API_IO_KEY` is present; failed odds requests clear stale odds data instead of showing old markets.

API-Football note: the free key tested here is quota-guarded at 100 requests/day and currently blocks the 2025 season, so current-season injuries and lineups are unavailable on that plan. The enrichment scripts fall back to the accessible 2024 season for historical xG/stat and squad-strength data.

[Back to top](#top)

## Themes

The app ships with **Day** and **Night** themes. The theme is selected automatically from the user's browser-local time:

- Day mode: 6 AM to 8 PM
- Night mode: 8 PM to 6 AM

[Back to top](#top)

## Local Setup

Create a `.env` file:

```bash
FOOTBALL_DATA_KEY=your_football_data_org_key_here
ODDS_PROVIDER=odds_api_io
ODDS_API_IO_KEY=your_odds_api_io_key_here
ODDS_API_IO_LEAGUE=france-ligue-1
ODDS_API_IO_BOOKMAKERS=DraftKings,BetMGM BR
ODDS_API_KEY=your_the_odds_api_key_here
API_FOOTBALL_KEY=your_api_football_key_here
API_FOOTBALL_DAILY_LIMIT=100
API_FOOTBALL_DAILY_RESERVE=10
```

Install dependencies and run the app:

```bash
pip install -r requirements.txt
streamlit run predictions.py
```

Run the full local pipeline:

```bash
python automation/nightly_pipeline.py
```

To preserve paid/free data-provider limits during testing:

```bash
python automation/nightly_pipeline.py --skip-odds
python automation/nightly_pipeline.py --skip-api-football
```

[Back to top](#top)

## Docs

See [docs/README.md](docs/README.md) for the full implementation roadmap and supporting notes.

[Back to top](#top)
