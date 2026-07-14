# Derived BTTS Features Integration Guide

This guide adds a safe fallback for **Both Teams To Score (BTTS)** when an
odds provider does not return a direct BTTS market. It preserves bookmaker
prices when they exist and otherwise derives a clearly labelled estimate from
the project's Poisson expected-goals model.

The result is intentionally not presented as a market price. That distinction
matters: direct BTTS odds contain bookmaker information that a model estimate
does not.

## What the feature means

`BTTS Yes` means both teams score at least one goal. Under independent Poisson
goal counts with expected goals `lambda_home` and `lambda_away`:

```text
P(BTTS Yes) = (1 - exp(-lambda_home)) * (1 - exp(-lambda_away))
P(BTTS No)  = 1 - P(BTTS Yes)
```

This is an estimate, not an exact derivation from 1X2 and total-goals odds.
Those markets do not uniquely identify a joint score distribution.

## Output contract

Keep direct market values separate from model values. The following schema is
recommended:

| Column | Meaning |
|---|---|
| `BTTSYesProb` / `BTTSNoProb` | Direct, vig-normalized bookmaker consensus. Leave blank if no direct BTTS market was fetched. |
| `ModelBTTSYesProb` / `ModelBTTSNoProb` | Probability calculated by the Poisson model. Never call these market odds. |
| `BTTSFeatureYesProb` / `BTTSFeatureNoProb` | The value a downstream model may consume: direct market value when both values exist, otherwise the Poisson value. |
| `BTTSFeatureSource` | `market` or `poisson_model`; use this for QA and analysis. |

This lets a downstream model use a complete feature while retaining provenance.
Do not overwrite `BTTSYesProb` with a model result.

## Prerequisites

The project needs a pre-match Poisson scorer. The example below uses these
functions:

```python
from models.poisson_predictor import compute_team_strengths, predict_match_poisson
```

`compute_team_strengths()` must accept historical matches containing
`HomeTeam`, `AwayTeam`, `FullTimeHomeGoals`, and `FullTimeAwayGoals`.
`predict_match_poisson()` must return a `BTTSProb` value from 0 to 1.

Install the normal numerical dependencies:

```bash
pip install pandas numpy scipy
```

## Drop-in implementation

Add this helper to the module that assembles your enriched match-level feature
store. `historical_path` should point to your completed-match training data;
`base` should have `HomeTeam` and `AwayTeam`, and may optionally already have
the direct market BTTS columns.

```python
from pathlib import Path

import pandas as pd

from models.poisson_predictor import compute_team_strengths, predict_match_poisson
from team_name_mapping import normalize_dataframe_teams


def add_btts_features(base: pd.DataFrame, historical_path: Path) -> pd.DataFrame:
    """Prefer direct BTTS odds; otherwise provide a labelled Poisson fallback."""
    out = base.copy()
    historical = pd.read_csv(historical_path)
    historical = normalize_dataframe_teams(historical)
    strengths = compute_team_strengths(historical)

    model_yes: list[float] = []
    for _, match in out.iterrows():
        prediction = predict_match_poisson(
            str(match.get("HomeTeam", "")),
            str(match.get("AwayTeam", "")),
            strengths,
        )
        model_yes.append(float(prediction["BTTSProb"]))

    out["ModelBTTSYesProb"] = model_yes
    out["ModelBTTSNoProb"] = (1 - out["ModelBTTSYesProb"]).round(4)

    def market_column(name: str) -> pd.Series:
        if name in out:
            return pd.to_numeric(out[name], errors="coerce")
        return pd.Series(float("nan"), index=out.index)

    market_yes = market_column("BTTSYesProb")
    market_no = market_column("BTTSNoProb")
    out["BTTSFeatureYesProb"] = market_yes.fillna(out["ModelBTTSYesProb"])
    out["BTTSFeatureNoProb"] = market_no.fillna(out["ModelBTTSNoProb"])
    out["BTTSFeatureSource"] = "poisson_model"
    out.loc[market_yes.notna() & market_no.notna(), "BTTSFeatureSource"] = "market"
    return out
```

Call it after joining market odds and after normalizing team names:

```python
base = add_btts_features(base, Path("data/model_ready_data.csv"))
base.to_csv("data/features/enriched_match_features.csv", index=False)
```

## Poisson scorer reference

If the destination project does not already have a Poisson scorer, this is the
essential BTTS calculation. Replace the two expected-goals values with your
own estimates (from a fitted model, team strengths, or rolling xG model).

```python
from math import exp


def btts_from_expected_goals(home_expected_goals: float, away_expected_goals: float) -> tuple[float, float]:
    yes = (1 - exp(-home_expected_goals)) * (1 - exp(-away_expected_goals))
    return round(yes, 4), round(1 - yes, 4)
```

For a full basic team-strength model:

```python
def expected_goals(home_attack, home_defense, away_attack, away_defense, league_home_avg, league_away_avg):
    home_xg = home_attack * away_defense * league_home_avg
    away_xg = away_attack * home_defense * league_away_avg
    return home_xg, away_xg
```

Use only pre-match information. For historical training rows, calculate team
strengths in a time-aware manner (for example, rolling values shifted by one
match) to avoid future leakage. A global all-history strength table is fine
for a simple current-fixture display but is not a valid backtest feature.

## Validation

Run these checks after each pipeline build:

```python
assert output["BTTSFeatureYesProb"].between(0, 1).all()
assert output["BTTSFeatureNoProb"].between(0, 1).all()
assert ((output["BTTSFeatureYesProb"] + output["BTTSFeatureNoProb"]).round(4) == 1).all()
assert output["BTTSFeatureSource"].isin(["market", "poisson_model"]).all()
```

Also monitor source coverage:

```python
print(output["BTTSFeatureSource"].value_counts(dropna=False))
```

If the provider starts returning BTTS later, the direct market probabilities
will automatically take precedence without deleting the model estimate.

## Implementation in this repository

The live implementation is in `build_enriched_features.py`. It writes the
columns above to `data_files/model_features/enriched_match_features.csv`.
Direct market BTTS columns continue to come from
`data_files/model_features/market_features.csv` when available.
