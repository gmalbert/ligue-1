# Ligue 1 Predictor — Architecture

## Overview
Streamlit multi-page app predicting Ligue 1 match outcomes and surfacing betting market value. Architecture mirrors La Liga Linea (sibling app in the Betting Oracle football suite).

## Data Flow
```
football-data.co.uk (F1.csv)    FBref (xG)    The Odds API   Coupe de France fixtures
        ↓                           ↓               ↓               ↓
fetch_historical_csvs.py     fetch_fbref_xg.py  fetch_odds.py  fetch_copa_fixtures.py
        ↓
data_files/combined_historical_data.csv
        ↓
utils.py → calculate_ligue1_features() [13 features, shift(1)]
        ↓
VotingClassifier (XGBoost×2 + RF×1.5 + GB×1 + LR×0.5, soft voting)
        ↓
models/ensemble_model.pkl
        ↓
predictions.py (entry) → pages/*.py
```

## ML Model
- **Target encoding**: A=0, D=1, H=2 (alphabetical)
- **`predict_proba` column order**: [P(Away), P(Draw), P(Home)]
- **Features**: 13 features, all `shift(1)` before rolling windows

## API Integrations
| Source | Purpose | Key |
|--------|---------|-----|
| football-data.co.uk | F1.csv per season | None (download) |
| football-data.org | Fixtures (FL1 competition) | `FOOTBALL_DATA_API_KEY` |
| FBref | xG stats (Ligue 1 comp ID) | None (scraped) |
| The Odds API | `soccer_france_ligue_one` | `ODDS_API_KEY` |
| odds-api.io | Alternative odds source | `ODDS_API_IO_KEY` |

## Theming System
Same as La Liga Linea — `themes.py` with `apply_theme()` + `plotly_theme()`. Auto day/night via browser hour. Use `render_table()` from `utils.py`, never `st.dataframe()` directly.

## Key Components
- `predictions.py` — entry, `st.set_page_config`, sidebar, `st.navigation`, theme init
- `utils.py` — ALL shared functions
- `themes.py` — day/night theming
- `team_name_mapping.py` — normalises team names across data sources
- `pages/*.py` — individual Streamlit pages (no `st.set_page_config`)
- `footer.py` — `add_betting_oracle_footer()`

## Storage
- `data_files/combined_historical_data.csv` — historical match data
- `data_files/upcoming_fixtures.csv` — scheduled fixtures
- `data_files/predictions_log.csv` — predictions log
- `data_files/raw/` — raw scraped data
- `models/ensemble_model.pkl` — trained ensemble (gitignored)
