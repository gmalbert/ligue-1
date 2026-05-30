# Outstanding Issues and Features

Reviewed: 2026-05-28

This file summarizes the remaining work found while reviewing all docs in `docs/`, excluding `moving_from_la_liga_to_ligue_1.md`.

## Correctness Issues

| Priority | Issue | Evidence | Suggested Fix |
|---|---|---|---|
| High | Best Bets and Sports Picks export appear to treat stored prediction percentages as probabilities. | `pages/predictions_tab.py` divides `PredHomeWin` by 100 for display math, but `pages/best_bets.py` and `scripts/export_best_bets.py` compare the raw `PredHomeWin` value directly to market implied probabilities. | Normalize prediction log probabilities to 0-1 everywhere, or divide by 100 before EV/edge calculations. |
| High | Neural network prediction logging is unlikely to run. | `automation/generate_predictions.py` looks for `FEATURE_COLS` inside the DataFrame returned by `predict_for_upcoming()`, but that function returns display columns, not raw model features. | Return feature vectors from `predict_for_upcoming()` or add a separate feature-builder used by both ensemble and NN predictions. |
| Medium | Backtest copy says out-of-sample, but the implementation scores the loaded model across the full engineered dataset. | `backtest.py` predicts over all historical rows after loading `models/ensemble_model.pkl`. | Recreate the same train/test split and evaluate only the held-out test rows, or implement walk-forward validation. |
| Medium | Keep-alive workflow still pings the old La Liga app URL. | `.github/workflows/keep-alive.yml` uses `https://la-liga-linea.streamlit.app/`. | Change it to the deployed Ligue Odds Streamlit URL. |
| Low | Several internal names still say La Liga or Copa. | Examples: `calculate_la_liga_features`, `compute_la_liga_standings`, `fetch_upcoming_pd_fixtures`, `LA_LIGA_AVG_HOME_GOALS`, and docs snippets. | Rename aliases gradually or keep aliases with clearly named Ligue 1 wrappers. |

## Outstanding Features

| Area | Outstanding Work |
|---|---|
| Predictions | Add Poisson as a selectable model in the UI and expose expected goals, BTTS, over/under, and scoreline markets. |
| Predictions | Add live score integration for in-progress Ligue 1 matches. |
| Predictions | Add PDF report export for matchday predictions. |
| Predictions | Add sidebar refresh button to clear cache and optionally trigger data refresh. |
| Best Bets | Add CSV download on the Markets page if the README promise should remain true. |
| Team Deep Dive | Add xG per game, Coupe de France load, and a cumulative form chart. |
| Data | Replace or augment the shot-on-target xG proxy with true FBref or Understat xG if reliable access is available. |
| Data | Add PSG squad availability and recently promoted club flags for Ligue 1-specific modeling. |
| Data | Add injury scraping/features. |
| Data | Add historical weather features to model training, not just upcoming fixture forecasts. |
| Data | Add KNN/smarter missing-data imputation if missingness becomes material. |
| Models | Add the LSTM momentum model or remove it from active roadmap language. |
| Infrastructure | Add a `tests/` suite and CI test step. |
| Infrastructure | Add shared rotating logging if local/nightly troubleshooting needs it. |
| Infrastructure | Decide whether SQLite/FastAPI remain roadmap items or should be dropped. |

## Documentation Cleanup

| Document | Remaining Cleanup |
|---|---|
| `docs/roadmap-features.md` | Many examples still use La Liga names/code snippets; status table now reflects the current Ligue Odds implementation. |
| `docs/roadmap-models.md` | Several examples still use `LaLigaNet` naming even though the app is Ligue 1. |
| `docs/roadmap-data.md` | Some source examples still refer to La Liga `PD`/`SP1`; status table now reflects `FL1`/`FR1`. |
| `docs/roadmap-layout.md` | Long code examples still show old `la_liga_linea.py` and numbered page names. |
| `docs/roadmap-infrastructure.md` | Long examples still include old app names and La Liga references. |
| `docs/la-liga.md` | Keep as expansion research only; it is not the active implementation roadmap. |
