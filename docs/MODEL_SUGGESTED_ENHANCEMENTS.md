# Ligue 1 Predictor — Model Suggested Enhancements

## Priority 1: Ensemble Improvements

### XGBoost Hyperparameter Tuning
- Run `Optuna` Bayesian optimisation on XGBoost, RandomForest, GradientBoosting independently.
- Current weights (XGB=2, RF=1.5, GB=1, LR=0.5) are shared from the La Liga template; validate them against Ligue 1's draw/home win distribution.

### Calibration
- Ligue 1's competitive balance creates more upsets; calibrate probability outputs with isotonic regression.
- Draw calibration curves per class (H, D, A) to find systematic bias.

## Priority 2: Ligue 1-Specific Features

### Coupe de France / Coupe de la Ligue Congestion
- Unlike Copa del Rey, French cup competitions have more participating rounds for top-tier clubs.
- Expand congestion flag to encode cup rounds within 3 days (not 4), as Ligue 1 squads are thinner.

### PSG Effect Adjustment
- PSG's squad depth creates a different fatigue profile vs. other clubs. Add a `is_psg` binary flag to apply appropriate handling.

### Relegated Clubs Downgrade
- Teams newly promoted from Ligue 2 tend to concede significantly in their first half-season. Encode `seasons_in_ligue1` (capped at 5) as a feature.

### xG Features from FBref
- FBref Ligue 1 xG data is scrapable. Ensure `xg_l5_home` and `xga_l5_away` are in `FEATURE_COLS`.

## Priority 3: Odds Integration

### Odds API Sport Key
- Sport key `soccer_france_ligue_one` confirmed. Use `fetch_odds.py` to pull live B365/William Hill lines at kick-off.

### Closing Line Value
- Record model probability at prediction time vs. closing decimal odds. Track weekly CLV as a model quality metric.

## Priority 4: Infrastructure

- Auto-delete `models/ensemble_model.pkl` at season start to force retraining on new Ligue 1 season data.
- Tag model version by training cutoff date for auditability.
