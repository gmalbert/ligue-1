# Ligue Odds — Roadmap Index

**App name:** Ligue Odds
**Framework:** Streamlit  
**League:** Ligue 1 (France) — competition code `FL1`
**Season:** August – May  
**DraftKings:** Decent market coverage
**Reviewed:** 2026-05-28

---

## What This App Does

Ligue Odds predicts the likely outcome of upcoming Ligue 1 matches (Home Win, Draw, Away Win) using historical match data, xG proxy metrics, bookmaker odds, and a multi-model ensemble. It also surfaces betting market context, team form, head-to-head history, Coupe de France fixture congestion, weather forecasts, and prediction performance in a Streamlit multi-page interface.

---

## Roadmaps

| Roadmap | What it covers |
|---|---|
| [Features Roadmap](roadmap-features.md) | All UI features, tabs, pages, and user-facing functionality |
| [Models Roadmap](roadmap-models.md) | ML model stack: ensemble, Poisson, neural network, LSTM, calibration |
| [Data Roadmap](roadmap-data.md) | Data sources, feature engineering, injury/weather/odds pipelines |
| [Data Enrichment Implementation](data-enrichment-implementation.md) | What was added for odds snapshots, API-Football, quota guards, and remaining gaps |
| [Layout Roadmap](roadmap-layout.md) | Streamlit page structure, sidebar, theming, multi-page navigation |
| [Infrastructure Roadmap](roadmap-infrastructure.md) | Automation, GitHub Actions, caching, logging, testing |
| [Quick Wins](roadmap-quick-wins.md) | Easy short-effort improvements with immediate impact |
| [Outstanding Issues and Features](outstanding-issues-and-features.md) | Remaining feature gaps, correctness risks, and stale-doc cleanup |

---

## Build Priority Status

```
Phase 1 — Foundation (Week 1-2)
  ├── ✅ Data pipeline: football-data.org FL1 fixtures + football-data.co.uk FR1 history
  ├── 🟡 xG proxy pipeline (true FBref/Understat xG still outstanding)
  ├── ✅ Feature engineering: form, rolling windows, rest days, odds, cup congestion
  ├── ✅ Ensemble model (XGBoost + RF + GB + LR)
  └── ✅ Core Streamlit app: multi-page navigation

Phase 2 — Enrichment (Week 3-4)
  ├── ✅ Odds integration (odds-api.io or The Odds API)
  ├── ✅ Odds snapshot feature store for market movement
  ├── 🟡 API-Football enrichment for injuries, lineups, squads, and match stats
  ├── ✅ Coupe de France congestion flag
  ├── 🟡 Poisson regression model implemented, not yet exposed in UI
  └── ✅ Statistics tab: team form, head-to-head, league averages

Phase 3 — Advanced (Month 2)
  ├── ✅ Neural network (PyTorch)
  ├── ⚪ LSTM momentum model
  ├── ✅ Markets page (EV engine, best bets)
  └── ✅ Prediction tracker (log + validate)

Phase 4 — Production (Month 3)
  ├── ✅ GitHub Actions nightly pipeline
  ├── ⚪ SQLite migration
  ├── ⚪ PDF report export
  └── 🟡 Mobile-responsive tuning
```

See [Outstanding Issues and Features](outstanding-issues-and-features.md) for the remaining work found during the documentation review.

---

## Project Structure (Current)

```
ligue-1/
├── predictions.py                # Main Streamlit entry point
├── footer.py                     # Shared footer (Betting Oracle branding)
├── themes.py                     # Streamlit theme helpers
├── team_name_mapping.py          # Normalize team names across sources
├── fetch_upcoming_fixtures.py    # Pull upcoming FL1 fixtures
├── fetch_fbref_xg.py             # Build xG proxy files from historical shots
├── fetch_odds.py                 # Pull market lines from odds-api.io or The Odds API
├── fetch_market_odds.py          # Append market snapshots and consensus features
├── fetch_xg_data.py              # API-Football match statistics/xG when available
├── fetch_lineups_injuries.py     # API-Football injuries and lineup cache
├── fetch_squad_strength.py       # API-Football squad cache and team depth features
├── build_enriched_features.py    # Join optional enrichment into a feature store
├── prepare_model_data.py         # Feature engineering pipeline
├── train_models.py               # Offline model training script
├── track_predictions.py          # Log and validate predictions
├── data_files/
│   ├── logo.png
│   ├── combined_historical_data.csv
│   ├── upcoming_fixtures.csv
│   └── raw/
│       ├── fbref_team_xg.csv
│       ├── match_xg.csv
│       ├── injuries.csv
│       ├── lineups.csv
│       ├── squad_strength.csv
│       ├── market_odds_snapshots.csv
│       └── odds.csv
│   └── model_features/
│       ├── market_features.csv
│       ├── availability_features.csv
│       └── enriched_match_features.csv
├── models/
│   ├── ensemble_model.pkl
│   ├── poisson_predictor.py
│   └── nn_predictor.py
├── pages/
│   ├── predictions_tab.py
│   ├── fixtures.py
│   ├── statistics.py
│   ├── team_deep_dive.py
│   ├── raw_data.py
│   ├── markets.py
│   ├── best_bets.py
│   └── performance.py
├── automation/
│   ├── nightly_pipeline.py
│   └── generate_predictions.py
├── docs/
│   ├── README.md            ← you are here
│   ├── la-liga.md
│   ├── ligue-1.md
│   ├── roadmap-features.md
│   ├── roadmap-models.md
│   ├── roadmap-data.md
│   ├── roadmap-layout.md
│   ├── roadmap-infrastructure.md
│   ├── roadmap-quick-wins.md
│   └── outstanding-issues-and-features.md
├── .github/workflows/
│   ├── keep-alive.yml
│   └── nightly.yml
├── requirements.txt
└── .gitignore
```

---

## Key Ligue 1 Differences from EPL/MLS

| Factor | EPL | MLS | Ligue 1 |
|---|---|---|---|
| API code (football-data.org) | `PL` | N/A | `FL1` |
| Historical CSV code | `E0` | N/A | `FR1` |
| xG source | FBref / API-Football | American Soccer Analysis | Current app uses xG proxy; true FBref/Understat remains outstanding |
| Referee data (English) | Playmaker Stats | N/A | Limited — simplify or drop |
| Fixture weeks | ~38 rounds | ~34 rounds + playoffs | ~34 rounds |
| Cup competition | FA Cup / EFL Cup | US Open Cup | Coupe de France |
| Average goals/game | ~2.8 | ~3.0 | ~2.6-2.8 |
| Dominant clubs | Man City, Liverpool | None (salary cap) | PSG dominance creates class imbalance |
| Stadium surface | All grass | ~25% turf | All grass |
| Travel fatigue | Low | Very high | Low-Medium |
