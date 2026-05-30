# Model Improvement Suggestions

## Current Read

The current 1X2 model is not failing because of a simple implementation bug. It is mostly matching the bookmaker-implied market baseline, which means the public-data feature set is not finding reliable edge in the most efficient headline market.

The latest full-season holdout shows the key issue:

- The model does not beat the market baseline.
- Draw recall is extremely weak.
- ROI is negative despite slightly positive CLV.
- The validation blend falls back fully to market probabilities.

## Recommended Direction

### 1. Stop Making 1X2 The Main Product

Home/draw/away is hard to beat. Move the core product toward markets that are more learnable from team and goal features:

- Over/under 2.5 goals
- Both teams to score
- Team totals
- Double chance
- Asian handicap

Keep 1X2 as a derived or secondary view.

### 2. Model Goals First

Build expected-goals or scoreline models first, then derive match result probabilities from simulated scorelines.

Useful approaches:

- Poisson model
- Dixon-Coles adjustment
- Team attack and defense ratings
- Home/away goal rates
- Recent xG/xGA form

This should improve draw handling because draws naturally emerge from score distributions.

### 3. Make The App Market-Comparison-First

The app should emphasize:

- Market probability
- Model probability
- Edge
- Confidence
- CLV
- No-bet conditions

Do not claim edge unless the model beats market log loss or shows positive CLV over time.

### 4. Add Real xG Data

The current shot/SOT proxy is useful but crude. True xG data would likely add more value than additional classifiers.

Prioritize:

- Team xG and xGA
- Rolling xG form
- Home/away xG splits
- Shot quality allowed
- Big chances created/conceded

### 5. Use CLV As A Primary Betting Metric

Accuracy is not enough for betting. Track whether recommended prices beat closing prices.

Important metrics:

- Average CLV
- CLV by market
- CLV by confidence tier
- ROI by CLV bucket
- Closing odds availability rate

### 6. Build A Dedicated Draw Model

Draws are currently underpredicted. Build a separate draw-likelihood model using:

- Market entropy
- Elo gap
- Expected goal difference
- Low total-goal expectation
- Similar team strength
- Defensive form
- Fixture congestion

Then blend draw probability back into 1X2 outputs.

### 7. Train Against Market Residuals

Do not ask the model to rediscover public strength information already priced into the market.

Instead, train residuals:

```text
model target = actual outcome - market expectation
```

The core question becomes: can the model identify where the market is wrong?

### 8. Weight Recent Seasons More

Older Ligue 1 seasons may no longer represent the current league environment.

Try:

- Last 3 seasons only
- Last 5 seasons only
- Exponential sample decay
- Separate treatment for promoted teams
- Current-season-only calibration layer

### 9. Add Squad And Schedule Context

Player availability may matter more than another classifier.

Useful additions:

- Injuries
- Suspensions
- Rotation risk
- European fixture congestion
- Rest asymmetry
- Travel
- Manager changes

### 10. Use Walk-Forward Model Selection

For each target market, compare:

- Market only
- Elo only
- Poisson
- XGBoost
- Neural network
- Market residual model
- Blended model

Only ship a model for a market if it beats the market baseline on walk-forward validation.

## Suggested Next Build

The most practical next modeling pass:

1. Build a goal-based Poisson/Dixon-Coles model.
2. Add over/under 2.5 and BTTS predictions.
3. Train residual models against market probabilities.
4. Make 1X2 a derived output from scoreline simulation.
5. Promote CLV and log-loss-vs-market as the headline model-quality metrics.

## Bottom Line

The current 1X2 model is too dependent on the market baseline to be useful as a standalone edge model. The best path forward is to pivot from exact match result prediction toward goal markets and market-residual modeling.
