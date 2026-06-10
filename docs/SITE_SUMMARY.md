> **AI Onboarding Guide** — See also `.github/copilot-instructions.md` for full coding conventions.

# Ligue 1 Predictor — Site Summary

## What This App Does

Streamlit multi-page app that predicts Ligue 1 (France) match outcomes and surfaces betting market value. It trains a soft-voting ensemble classifier on historical match data, compares model probabilities against live bookmaker odds, and displays predictions with edge percentages. Architecture is nearly identical to the La Liga Linea sibling app.

## Quick Start

```bash
# 1. Activate virtual environment
.\.venv\Scripts\Activate.ps1        # Windows
source .venv/bin/activate           # macOS/Linux

# 2. (Optional) Refresh data
python fetch_historical_csvs.py     # Download F1.csv for recent seasons
python fetch_upcoming_fixtures.py   # Fetch next scheduled Ligue 1 fixtures
python fetch_odds.py                # Fetch live Ligue 1 odds

# 3. Run the app
streamlit run predictions.py
```

## Tech Stack

| Layer | Technology |
|---|---|
| UI | Streamlit ≥1.36 (`st.navigation` + `st.Page`) |
| ML | VotingClassifier: XGBoost×2, RF×1.5, GB×1, LR×0.5 (soft voting) |
| Data | pandas, NumPy |
| Visualization | Plotly Express |
| Scraping | requests, BeautifulSoup4, lxml |
| Config | python-dotenv (`.env` file) |
| PDF export | fpdf2 |

## Key Files

| File | Purpose |
|---|---|
| `predictions.py` | Entry point — `st.set_page_config`, sidebar, `st.navigation`, theme injection, auto day/night detection |
| `utils.py` | **All** shared functions: data loading, feature engineering, model training, display helpers |
| `pages/*.py` | Individual Streamlit pages — never call `st.set_page_config` here |
| `footer.py` | `add_betting_oracle_footer()` — called in `predictions.py` after `pg.run()` |
| `themes.py` | `apply_theme()` and `plotly_theme()` — called before `pg.run()` |
| `team_name_mapping.py` | Name normalization across data sources |
| `data_files/combined_historical_data.csv` | Historical Ligue 1 seasons from football-data.co.uk |
| `models/ensemble_model.pkl` | Trained VotingClassifier (auto-generated; delete to force retrain) |

## Data Flow

1. **Historical data**: `fetch_historical_csvs.py` downloads `F1.csv` per season (football-data.co.uk) → `data_files/combined_historical_data.csv`
2. **Upcoming fixtures**: `fetch_upcoming_fixtures.py` hits football-data.org `FL1` endpoint → `data_files/upcoming_fixtures.csv`
3. **Feature engineering**: `calculate_features()` in `utils.py` — groupby rolling with `shift(1)` to prevent data leakage
4. **Training**: `VotingClassifier` trained in `utils.py` → saved to `models/ensemble_model.pkl`
5. **Live odds** (optional): `fetch_odds.py` using `soccer_france_ligue_one` → `data_files/raw/`
6. **UI**: Streamlit reads CSVs + loads model → renders predictions, value bets, fixture context

## Environment Variables

| Variable | Purpose | Required |
|---|---|---|
| `ODDS_API_KEY` | The Odds API — live Ligue 1 odds (`soccer_france_ligue_one`) | Optional |
| `FOOTBALL_DATA_ORG_API_KEY` | football-data.org — upcoming FL1 fixtures | Optional |

## External APIs & Rate Limits

| API | Notes |
|---|---|
| football-data.co.uk | Static CSV download, no key needed; file is `F1.csv` |
| football-data.org | Competition code `FL1`; 10 req/min free tier |
| The Odds API | `soccer_france_ligue_one`; 500 req/month free tier |

## Critical Conventions

- **Never** call `st.set_page_config()` in `pages/*.py` — only in `predictions.py`
- **Always** use `render_table(df)` from `utils.py` instead of `st.dataframe()` directly
- **Always** call `fig.update_layout(**plotly_theme())` on every Plotly figure
- **Always** use `shift(1)` before `.rolling(n).mean()` to prevent data leakage
- **Always** normalize team names via `team_name_mapping.py` before merging sources
- Target encoding: A=0, D=1, H=2 → `predict_proba` column order is [P(Away), P(Draw), P(Home)]
- All ML logic lives in `utils.py` — pages only display

## Common Gotchas

- Pandas Styler row colors in day mode must use **solid opaque hex** — rgba renders dark-on-dark on the canvas renderer
- Adding a feature: (1) add to `FEATURE_COLS`, (2) implement in feature engineering function, (3) delete `models/ensemble_model.pkl`, (4) mirror in the upcoming-fixtures stats function
- Day/night auto-detection uses a JS snippet injecting `?hour=H` into the URL
- No turf/surface flag needed — all Ligue 1 stadiums use natural grass
- European competition (Champions League / Europa League) fatigue is a Ligue 1-relevant feature; Copa-style scripts may need adaptation for French cups
