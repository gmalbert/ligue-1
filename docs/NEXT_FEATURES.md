# Ligue 1 Predictor — Next 5 Features to Implement

> **Based on:** Codebase gap analysis as of July 2025

---

## Feature 1: European Competition Fatigue Feature

**Why:** Ligue 1 clubs in Champions League or Europa League play Thursday/Sunday cycles and travel long distances mid-week. This is a meaningful signal not captured by the current 13-feature set, and it is the single biggest structural difference between Ligue 1 and La Liga modeling.

**How:**
1. Fetch Champions League / Europa League fixtures via `fetch_copa_fixtures.py` (adapt it for UEFA via football-data.org `CL` and `EL` competition codes)
2. Create a binary feature `home_eur_fatigue` / `away_eur_fatigue`: 1 if team played a UEFA match ≤5 days before this Ligue 1 game
3. Add to `FEATURE_COLS` in `utils.py` with `shift(1)` guard
4. Update `_team_stats_for_upcoming()` for the same feature

**Complexity:** Medium

---

## Feature 2: Relegation/Promotion Zone Incentive Feature

**Why:** Teams battling relegation at the bottom of Ligue 1 (positions 16–18) perform differently under pressure than mid-table clubs. Encoding how many points a team is above/below the relegation line improves prediction quality in late-season matches.

**How:**
1. Fetch live Ligue 1 standings from football-data.org or ESPN API
2. Compute `home_pts_above_relegation` and `away_pts_above_relegation` integers (negative = in drop zone)
3. Add these to `FEATURE_COLS` in `utils.py`
4. Use `shift(1)` — apply the standings position as of the last played matchday

**Complexity:** Medium

---

## Feature 3: Live Line Movement Tracker

**Why:** Storing opening vs current spreads reveals sharp action and public bias. The `fetch_odds.py` script already calls The Odds API (`soccer_france_ligue_one`) but does not store time-series snapshots.

**How:**
1. Add `data_files/raw/odds_snapshots_ligue1.csv` with columns: `fixture_id`, `snapshot_time`, `home_odds`, `draw_odds`, `away_odds`
2. Modify the GitHub Action to call `fetch_odds.py` twice — once at T-48h and once at T-2h before kickoff
3. Add `pages/line_movement.py` with a Plotly line chart per upcoming fixture showing the snapshots over time

**Complexity:** Medium

---

## Feature 4: Historical Backtesting Page

**Why:** The model has no UI for evaluating its past accuracy on a season-by-season basis. A walk-forward backtest page showing ROI, accuracy, and Brier score per season would build user trust and highlight where the model underperforms (e.g., early season, post-winter break).

**How:**
1. Add `backtest.py` (or adapt existing one if present) to replay predictions using `shift(1)` on each season
2. Compute: per-season accuracy (H/D/A), Brier score, ROI at flat stake on model's top-confidence picks
3. Add `pages/backtesting.py` with a Plotly bar chart per season + summary metrics table

**Complexity:** Medium

---

## Feature 5: Player News / Injury Integration

**Why:** A single key absence (striker, goalkeeper) can shift the model's accuracy significantly. Ligue 1 injury reports are available via the ESPN or the football-data.org API.

**How:**
1. Add `fetch_injuries.py` that calls ESPN's Ligue 1 injury endpoint (or football-data.org roster endpoint)
2. Write `data_files/raw/injuries_ligue1.json` with team → player list of unavailable players
3. On each prediction card in the Today page, display an injury warning if 2+ key players are listed for that team
4. Do not use injury data as a model feature (requires too much structure) — show it as a contextual flag only

**Complexity:** Low
