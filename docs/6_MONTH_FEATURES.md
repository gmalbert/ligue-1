# Ligue 1 Predictor — 6-Month Feature Roadmap

## Month 1: Match Day

- **Weekend fixture view** — All Ligue 1 matches this round with model H/D/A probabilities.
- **Live score banner** — Auto-refreshing scores for in-play matches via ESPN API.
- **Form badges** — "Won last 3" / "No win in 5" indicators on team matchup cards.
- **Top scorer leaderboard** — Current season goals and assists leaders.

## Month 2: Team Intelligence

- **Team profile page** — Season stats, xG trend, squad depth, form chart.
- **Home advantage rating** — Visual indicator of teams with strong/weak home records.
- **Cup congestion tracker** — Flag teams playing Coupe de France in the same week.

## Month 3: Betting Tools

- **Value bet table** — Filter where model edge vs. B365 exceeds 3%.
- **Draw finder** — Historically draw-heavy fixtures highlighted (Ligue 1 draw rate ~25%).
- **Odds comparison** — B365, Unibet, no-vig model probability side by side.

## Month 4: Analytics

- **Season accuracy report** — Model performance broken down by team and outcome class.
- **PSG performance analysis** — Historical accuracy vs. expectation when PSG plays.
- **Relegation zone insights** — Probability of each bottom-3 team avoiding relegation.

## Month 5: Export & Reports

- **PDF matchday export** — One-click PDF of all weekend Ligue 1 predictions with odds.
- **Season summary report** — End-of-season accuracy and CLV report.

## Month 6: Automation

- **Nightly fixture fetch** — GitHub Action runs `fetch_upcoming_fixtures.py` and `fetch_odds.py`.
- **Friday email** — Weekly predictions email with weekend fixture summary.
- **Model retraining trigger** — Monthly Action to retrain on current-season data.
