# Data Enrichment Implementation

## Implemented

- `fetch_market_odds.py` stores append-only odds snapshots in `data_files/raw/market_odds_snapshots.csv`.
- `fetch_market_odds.py` also builds `data_files/model_features/market_features.csv`.
- `api_football_client.py` centralizes API-Football calls behind a local daily quota guard.
- `fetch_xg_data.py` pulls API-Football match statistics and true xG when available.
- `fetch_lineups_injuries.py` pulls injuries and lineups when the plan allows current-season access.
- `fetch_squad_strength.py` caches teams/squads and builds `data_files/raw/squad_strength.csv`.
- `build_enriched_features.py` joins optional enrichment into `data_files/model_features/enriched_match_features.csv`.

## Current Provider Limits

- odds-api.io is integrated and working, but Ligue 1 currently has no pending/live events, so market snapshots are empty until fixtures return.
- API-Football is guarded at `API_FOOTBALL_DAILY_LIMIT=100` with a default reserve of 10 requests.
- The tested API-Football key blocks the 2025 season and allows historical seasons through 2024.
- API-Football also blocks the `last` fixture parameter on this plan, so the xG script uses a date-window fallback.
- Squad pulls need a delay between team requests to avoid per-minute throttling.

## Gaps

- Current-season injuries, suspensions, expected lineups, and confirmed lineups require an API-Football plan with current-season access.
- Missing starter count, missing minutes share, unavailable xG/xA share, and lineup continuity need player-minute history plus current availability data.
- Market movement, opener, closing line, implied totals, BTTS, and CLV need live odds snapshots after Ligue 1 fixtures are available again.
- The enriched feature store is additive only; the production model does not yet train on these new fields.
