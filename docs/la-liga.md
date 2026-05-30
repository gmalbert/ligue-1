# La Liga (Spain)

**Tier: A** | Season: August–May | DraftKings: Full markets

## Review Status

- 🟡 This document is retained as expansion research, but it is no longer the active implementation target for this repository.
- ✅ The current app has been ported to Ligue 1 as **Ligue Odds**.
- ⚪ If La Liga support is revived later, the remaining work should be tracked separately from the Ligue 1 roadmaps.
- Reviewed: 2026-05-28

## Data Sources

- `football-data.org` (free tier — fixtures, results, standings, odds)
- `API-Football` (freemium — deeper stats)
- FBref (scrapeable — xG, possession, advanced metrics)
- The Odds API (market lines)

## Overview

La Liga is the most natural first expansion for Betting Oracle after the Premier League. The data pipeline is structurally identical — same APIs, same feature set, same model architecture. In terms of development effort, porting your EPL model to La Liga is closer to a configuration change than a rebuild. The main differences are tactical and cultural: La Liga trends toward more possession-heavy, technically precise football, with slightly lower scoring than the EPL on average.

With clubs like Real Madrid, Barcelona, Atletico Madrid, and Villarreal, La Liga carries massive global betting interest, and DraftKings reflects that with deep market coverage. It's also one of the five leagues explicitly covered by football-data.org's free tier.

---

## Pros

- **Near copy-paste of your EPL infrastructure.** football-data.org covers La Liga under the same API schema as the Premier League. Your data pulls, feature engineering, and model pipeline require almost no changes — just swap the league code and retrain.
- **football-data.org free tier explicitly covers La Liga.** Fixtures, results, standings, top scorers, head-to-head records — all available without paying.
- **Rich FBref historical data.** FBref covers La Liga with the same depth as EPL: xG, xGA, possession stats, passing networks, defensive actions. Going back to 2014–15, you have a decade of advanced data for model training.
- **High DraftKings market depth.** Moneyline (1X2), Asian handicap, totals, both teams to score, first goalscorer, and correct score markets are all available. Liquidity is second only to EPL among European leagues.
- **Complementary schedule to EPL.** La Liga runs on the same August–May calendar with slightly offset fixture weeks. Publishing picks for both leagues simultaneously gives you more content without more infrastructure.
- **Strong public betting interest.** El Clásico (Real Madrid vs. Barcelona) is one of the most-bet soccer matches in the world. Major fixtures drive significant traffic and engagement.

---

## Cons

- **Less public model research vs. EPL.** The EPL has a huge community of public quant bettors publishing research, benchmarks, and Elo ratings. La Liga has less of this — fewer external baselines to compare your model against.
- **Mid-table team data is thinner.** The top 6–8 La Liga clubs have rich scouting data, media coverage, and lineup reporting in English. Mid-table clubs like Getafe, Osasuna, or Celta Vigo have less English-language news coverage, making injury and lineup monitoring harder.
- **Tactical variety requires model awareness.** La Liga includes a wider range of tactical styles than EPL — from Barcelona's high-press possession game to Atletico's deep defensive block. These stylistic matchup effects are real but harder to encode than simple form metrics.
- **Referee assignment data is harder to source** in La Liga than in EPL, where referee statistics are widely reported in English. Your EPL model includes referee tendencies; you may need to drop or simplify that feature for La Liga.

---

## Recommended Build Approach

**Primary model targets:** 1X2 match result, both teams to score, over/under 2.5 goals, Asian handicap.

**Key features to engineer:**
- xG and xGA (last 5 games, exponentially weighted)
- Home/away form split (last 10 games each)
- Head-to-head results (last 5 meetings)
- Days rest between fixtures (La Liga has fewer midweek games than EPL)
- League position differential
- Goals scored/conceded per game (rolling 10-game window)
- Copa del Rey fixture congestion flag

**Data pipeline:**
```python
import requests

API_KEY = "your_football_data_org_key"
BASE_URL = "https://api.football-data.org/v4"

headers = {"X-Auth-Token": API_KEY}

# La Liga is competition code PD (Primera Division)
fixtures = requests.get(f"{BASE_URL}/competitions/PD/matches", headers=headers)
standings = requests.get(f"{BASE_URL}/competitions/PD/standings", headers=headers)
```

For xG data, scrape FBref's La Liga team stats page — the structure is identical to EPL scrapes you've already built.

**Suggested model stack:** Reuse your EPL ensemble (XGBoost + Random Forest + Gradient Boosting + Logistic Regression). Retrain on La Liga data only — don't mix with EPL data, as the leagues have different scoring distributions and styles. Run separate calibration against closing lines.

**Backtesting window:** 2015–16 through 2023–24 gives you 9 seasons. With 380 games per season that's ~3,400 training examples — solid for an ensemble model.

---

## Build Priority

**High — do this immediately after (or alongside) the other European leagues.** The marginal development cost is extremely low given your existing EPL work. La Liga + Bundesliga + Serie A can reasonably be shipped as a batch expansion, tripling your European soccer coverage with minimal additional engineering.
