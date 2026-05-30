# Ligue 1 (France)

**Tier: B** | Season: August–May | DraftKings: Decent markets

## Implementation Status

- ✅ Ligue 1 app exists as **Ligue Odds** with Streamlit navigation, prediction pages, fixtures/standings, statistics, markets, best bets, raw data, and performance tracking.
- ✅ Core data sources are implemented for `FL1` fixtures, `FR1.csv` historical data, The Odds API, Coupe de France congestion, and Open-Meteo forecasts.
- 🟡 xG currently uses a shot-on-target proxy from historical data instead of Understat/FBref.
- ⚪ Remaining Ligue 1-specific model ideas: PSG squad availability flag and recently promoted club flag.
- Reviewed: 2026-05-28

## Data Sources

- `football-data.org` (free tier — fixtures, results, standings)
- Understat.com (free xG data, scrapeable)
- FBref (scrapeable — advanced metrics)
- The Odds API (market lines)

## Overview

Ligue 1 is the fifth of Europe's "Big Five" leagues and the most straightforward to add if you're already shipping La Liga, Bundesliga, and Serie A. The data pipeline is identical — football-data.org, Understat, and FBref all cover it with the same schemas. The main challenge is less technical and more structural: PSG's financial dominance creates a league with one giant club and 17 competitors, which produces class imbalance and limits the pool of genuinely competitive matches.

That said, Ligue 1 clubs regularly compete deep in the Champions League, the league produces some of the world's best individual talents (Mbappé, Benzema came through here), and DraftKings carries it as part of their European soccer offerings. As a bundle add-on to the other European leagues, the development cost is essentially zero.

---

## Pros

- **Truly a 5-minute port from the other European leagues.** football-data.org league code FL1. Same Understat scraper with `league="Ligue_1"`. Same FBref structure. If you've built La Liga and Bundesliga, Ligue 1 is a configuration change.
- **PSG dominance creates exploitable spreads against mid-table opponents.** When PSG's full squad is available, the line against a mid-table Ligue 1 side is often -1.5 or greater, but their home form metrics justify it. There's potential value in correctly identifying when PSG is likely to underperform (heavy rotation, Champions League fatigue).
- **Understat xG coverage is excellent and consistent.** Same methodology as all other Understat leagues, going back to 2014. No extra data sourcing work.
- **UCL connection.** Ligue 1 clubs (especially PSG and Olympique Lyonnais historically) participate in the Champions League. If you've built a UCL model, your Ligue 1 club strength ratings feed directly into it.

---

## Cons

- **PSG dominance creates severe class imbalance.** In seasons with a fully functioning PSG squad, they win the title by 10–15 points and beat most opponents convincingly. A logistic regression model trained on Ligue 1 will assign very high win probabilities to PSG in nearly every match — which is correct but not actionable for bettors. The picks content is less interesting.
- **Smaller US betting public interest = less DraftKings liquidity.** Compared to EPL or La Liga, the US betting market for Ligue 1 is thinner. Fewer major-market clubs (PSG is the exception) means prop markets and in-play options are limited outside of big matches.
- **Some fixture data gaps in free-tier APIs.** football-data.org's free tier for Ligue 1 is solid but has occasionally shown gaps for earlier rounds of the season compared to EPL coverage. Worth testing the data completeness before building.
- **Tactical diversity below the top 3 clubs is limited.** The mid-table Ligue 1 clubs — Rennes, Nantes, Reims, Strasbourg — follow fairly predictable tactical patterns that don't generate as much model-interesting variation as EPL or Bundesliga mid-table.
- **Relegation and promotion volatility.** Ligue 1 promotes 3 teams from Ligue 2 each season. Newly promoted clubs have very limited top-flight data history, which degrades model accuracy in their early season matches.

---

## Recommended Build Approach

**Primary model targets:** 1X2 match result, both teams to score, over/under 2.5 goals, Asian handicap.

**Key features to engineer:**
- xG and xGA (Understat, last 5 and 10 games)
- PSG squad availability flag (designated player equivalent — single biggest swing factor in the league)
- Form points (last 5 games)
- Recently promoted club flag (first 10 games of season for Ligue 2 promotees)
- Head-to-head at venue

**Understat data pull:**
```python
import understatapi

client = understatapi.UnderstatClient()

matches = client.league(league="Ligue_1").get_match_data(season="2023")
team_stats = client.league(league="Ligue_1").get_team_data(season="2023")
```

**Calibration note:** PSG matches will dominate your model's high-confidence picks. Consider filtering or flagging these separately in your UI — "dominant favorite" picks have different betting utility than genuinely competitive matches.

**Backtesting window:** 2014–15 through 2023–24 (10 seasons, ~3,800 games).

---

## Build Priority

**Medium — add as part of the European leagues bundle, but not a standalone priority.** Ligue 1 is worth including for completeness and because the marginal cost is zero if you're already building the other four leagues. It should not be a standalone build — bundle it with La Liga, Bundesliga, and Serie A as a single "five major leagues" expansion. The PSG dominance issue limits its standalone value as a picks source.
