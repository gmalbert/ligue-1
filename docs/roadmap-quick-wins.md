# Quick Wins Roadmap — Ligue Odds

## Status
- ✅ 9 of 10 quick wins are implemented in the current Ligue Odds app.
- ⚪ Outstanding: sidebar refresh button.
- Reviewed: 2026-05-28

## Overview

Each item here takes **≤ 15 minutes** to implement and delivers immediate visible impact. Add these incrementally after the core app is working. Total estimated effort: ~35 minutes for all 10.

---

## 1. Match Commentary Generator
**Effort:** 5 min | **Impact:** High (makes predictions feel alive)

Generates a natural-language one-liner for each upcoming match.

```python
# utils/commentary.py

def generate_match_commentary(
    home_team: str,
    away_team: str,
    home_win_prob: float,
    draw_prob: float,
    away_win_prob: float,
    risk_category: str,
) -> str:
    """Return a single natural-language sentence summarising the prediction."""
    top_prob = max(home_win_prob, draw_prob, away_win_prob)
    if home_win_prob == top_prob:
        top_label = f"{home_team} to win"
    elif away_win_prob == top_prob:
        top_label = f"{away_team} to win"
    else:
        top_label = "a draw"

    conf_word = (
        "confident" if top_prob >= 0.60
        else "leaning" if top_prob >= 0.45
        else "uncertain about"
    )

    risk_phrase = {
        "Low":      "This looks like a solid bet.",
        "Moderate": "Worth a small stake.",
        "High":     "High variance — consider smaller units.",
        "Critical": "Proceed with caution; model uncertainty is high.",
    }.get(risk_category, "")

    return (
        f"The model is {conf_word} on **{top_label}** at "
        f"{top_prob:.0%} confidence. {risk_phrase}"
    )


# In la_liga_linea.py predictions table loop:
# for _, row in predictions_df.iterrows():
#     commentary = generate_match_commentary(
#         row["HomeTeam"], row["AwayTeam"],
#         row["PredHomeWin"], row["PredDraw"], row["PredAwayWin"],
#         row["RiskCategory"]
#     )
#     st.caption(commentary)
```

---

## 2. Color-Coded Confidence Display
**Effort:** 3 min | **Impact:** High (instant visual scanning)

```python
# Already referenced in roadmap-features.md; reproduced here for completeness

def color_confidence(prob: float) -> str:
    """Return a CSS color string for a win probability."""
    if prob >= 0.60:
        return "color: #2ecc71; font-weight: bold"   # green
    elif prob >= 0.45:
        return "color: #f39c12; font-weight: bold"   # amber
    else:
        return "color: #e74c3c"                       # red

# Streamlit usage with st.markdown (inline):
# prob_str = f"{row['PredHomeWin']:.0%}"
# st.markdown(f"<span style='{color_confidence(row[\"PredHomeWin\"])}'>{prob_str}</span>",
#             unsafe_allow_html=True)


# Alternatively, with DataFrame styling:
def color_risk_rows(row: pd.Series) -> list[str]:
    """Apply a background tint to the whole row based on RiskCategory."""
    color_map = {
        "Low":      "background-color: rgba(46,204,113,0.15)",
        "Moderate": "background-color: rgba(243,156,18,0.15)",
        "High":     "background-color: rgba(231,76,60,0.15)",
        "Critical": "background-color: rgba(192,57,43,0.25)",
    }
    style = color_map.get(row.get("RiskCategory", ""), "")
    return [style] * len(row)
```

---

## 3. CSV Download Button
**Effort:** 2 min | **Impact:** Medium (power-user feature)

```python
import streamlit as st
import pandas as pd
from datetime import datetime

def add_csv_download_button(df: pd.DataFrame, filename_prefix: str = "la_liga") -> None:
    """Add a styled download button below any DataFrame."""
    today = datetime.now().strftime("%Y%m%d")
    csv_bytes = df.to_csv(index=False).encode("utf-8")
    st.download_button(
        label="📥 Download as CSV",
        data=csv_bytes,
        file_name=f"{filename_prefix}_{today}.csv",
        mime="text/csv",
        help="Download the current view as a CSV file.",
    )


# Usage — drop anywhere after an st.dataframe() call:
# add_csv_download_button(predictions_df, filename_prefix="la_liga_predictions")
# add_csv_download_button(standings_df,   filename_prefix="la_liga_standings")
```

---

## 4. Last-Update Timestamp Banner
**Effort:** 2 min | **Impact:** Medium (builds user trust)

```python
import streamlit as st
import os
from datetime import datetime

def show_last_updated(file_path: str, label: str = "fixtures") -> None:
    """Show a small caption with how long ago the data file was last modified."""
    if not os.path.exists(file_path):
        return
    mtime = datetime.fromtimestamp(os.path.getmtime(file_path))
    delta = datetime.now() - mtime
    hours, minutes = int(delta.total_seconds() // 3600), int((delta.total_seconds() % 3600) // 60)

    if hours >= 24:
        age = f"{hours // 24}d ago"
    elif hours >= 1:
        age = f"{hours}h {minutes}m ago"
    else:
        age = f"{minutes}m ago"

    st.caption(f"🕐 {label.capitalize()} last updated: **{mtime.strftime('%Y-%m-%d %H:%M')}** ({age})")


# Usage:
# show_last_updated("data_files/upcoming_fixtures.csv", label="fixtures")
# show_last_updated("models/ensemble_model.pkl",        label="model")
```

---

## 5. Team Filter Dropdown
**Effort:** 3 min | **Impact:** Medium (navigability)

```python
import streamlit as st
import pandas as pd

def add_team_filter(df: pd.DataFrame, team_col_home: str = "HomeTeam",
                    team_col_away: str = "AwayTeam") -> pd.DataFrame:
    """
    Render a team multi-select widget and return the filtered DataFrame.
    Pass the result back into st.dataframe().
    """
    all_teams = sorted(
        set(df[team_col_home].dropna().unique()) |
        set(df[team_col_away].dropna().unique())
    )
    selected = st.multiselect(
        "Filter by team:",
        options=all_teams,
        default=[],
        placeholder="All teams",
    )
    if selected:
        mask = df[team_col_home].isin(selected) | df[team_col_away].isin(selected)
        return df[mask]
    return df


# Usage in _tab_predictions():
# display_df = add_team_filter(display_df)
# st.dataframe(display_df, width='stretch', hide_index=True)
```

---

## 6. Date Range Filter
**Effort:** 3 min | **Impact:** Medium

```python
import streamlit as st
import pandas as pd
from datetime import date, timedelta

def add_date_filter(df: pd.DataFrame, date_col: str = "Date") -> pd.DataFrame:
    """
    Render a date slider and return the filtered DataFrame.
    Expects df[date_col] to be parseable as a date.
    """
    df = df.copy()
    df[date_col] = pd.to_datetime(df[date_col], errors="coerce")
    df = df.dropna(subset=[date_col])

    if df.empty:
        return df

    min_d = df[date_col].min().date()
    max_d = df[date_col].max().date()

    default_start = max(min_d, date.today())
    default_end   = min(max_d, date.today() + timedelta(weeks=4))

    col1, col2 = st.columns(2)
    start_d = col1.date_input("From:", value=default_start, min_value=min_d, max_value=max_d)
    end_d   = col2.date_input("To:",   value=default_end,   min_value=min_d, max_value=max_d)

    mask = (df[date_col].dt.date >= start_d) & (df[date_col].dt.date <= end_d)
    return df[mask]


# Usage:
# display_df = add_date_filter(display_df, date_col="Date")
```

---

## 7. Top Features Bar Chart (Model Explainability)
**Effort:** 5 min | **Impact:** High (educates users on what drives predictions)

```python
import streamlit as st
import plotly.express as px
import pandas as pd
import pickle

def show_feature_importance_chart(
    model_path: str = "models/ensemble_model.pkl",
    feature_names: list[str] | None = None,
    top_n: int = 15,
) -> None:
    """Render a Plotly horizontal bar chart of top XGBoost feature importances."""
    try:
        with open(model_path, "rb") as f:
            model = pickle.load(f)
    except FileNotFoundError:
        st.info("Train the model first to see feature importance.")
        return

    # Extract XGBoost estimator from the VotingClassifier
    xgb_estimator = None
    for name, est in getattr(model, "estimators_", []):
        if hasattr(est, "feature_importances_"):
            xgb_estimator = est
            break

    if xgb_estimator is None:
        st.info("Feature importance not available for this model type.")
        return

    importances = xgb_estimator.feature_importances_
    if feature_names is None:
        feature_names = [f"Feature {i}" for i in range(len(importances))]

    fi_df = (
        pd.DataFrame({"Feature": feature_names, "Importance": importances})
        .sort_values("Importance", ascending=True)
        .tail(top_n)
    )

    fig = px.bar(
        fi_df,
        x="Importance",
        y="Feature",
        orientation="h",
        title=f"Top {top_n} Model Features",
        color="Importance",
        color_continuous_scale="Reds",
    )
    fig.update_layout(
        height=400,
        showlegend=False,
        coloraxis_showscale=False,
        margin={"l": 0, "r": 0, "t": 40, "b": 0},
    )
    st.plotly_chart(fig, width='stretch')


# Usage (inside _tab_statistics or predictions tab):
# with st.expander("🔍 What drives the model?"):
#     show_feature_importance_chart(feature_names=feature_names)
```

---

## 8. Sidebar Refresh Button
**Effort:** 2 min | **Impact:** Medium (power-user QoL)

Already included in [roadmap-layout.md](roadmap-layout.md) sidebar section. Extracted here for standalone reference:

```python
# In la_liga_linea.py sidebar section

if st.sidebar.button("🔄 Refresh All Data", width='stretch'):
    # Clear the Streamlit cache so next load re-fetches everything
    st.cache_data.clear()
    st.sidebar.success("Cache cleared — reload page to refresh.")

    # Optionally trigger pipeline scripts:
    # import subprocess
    # subprocess.Popen(["python", "automation/nightly_pipeline.py"])
```

---

## 9. Match Countdown Timer
**Effort:** 3 min | **Impact:** Medium (engagement)

Already included in [roadmap-layout.md](roadmap-layout.md) sidebar section. Extracted here for standalone reference:

```python
# utils/countdown.py
import pandas as pd
from datetime import datetime

def get_next_match_countdown(upcoming_df: pd.DataFrame) -> dict | None:
    """
    Return a dict with match details and time remaining until next kickoff.
    Returns None if no upcoming matches or all times have passed.
    """
    if upcoming_df is None or upcoming_df.empty:
        return None

    df = upcoming_df.copy()
    df["DateTime"] = pd.to_datetime(
        df["Date"].astype(str) + " " + df.get("Time", pd.Series(["12:00 PM"] * len(df))).astype(str),
        errors="coerce",
    )
    future = df[df["DateTime"] > datetime.now()].sort_values("DateTime")
    if future.empty:
        return None

    nxt   = future.iloc[0]
    delta = nxt["DateTime"] - datetime.now()
    d     = delta.days
    h     = delta.seconds // 3600
    m     = (delta.seconds % 3600) // 60

    return {
        "home":       nxt.get("HomeTeam", "?"),
        "away":       nxt.get("AwayTeam", "?"),
        "kickoff":    nxt["DateTime"].strftime("%a %b %d, %H:%M"),
        "days":       d,
        "hours":      h,
        "minutes":    m,
        "countdown":  f"{d}d {h}h {m}m",
    }
```

---

## 10. Progress Columns in DataFrames
**Effort:** 5 min | **Impact:** Medium (probability bars make scanning easier)

```python
import streamlit as st
import pandas as pd

def render_predictions_with_progress_bars(predictions_df: pd.DataFrame) -> None:
    """
    Render predictions DataFrame with probability columns shown as progress bars.
    Expects columns: HomeTeam, AwayTeam, Date, PredHomeWin, PredDraw, PredAwayWin.
    """
    required = ["HomeTeam", "AwayTeam", "Date", "PredHomeWin", "PredDraw", "PredAwayWin"]
    if not all(c in predictions_df.columns for c in required):
        st.dataframe(predictions_df, hide_index=True, width='stretch')
        return

    st.dataframe(
        predictions_df,
        hide_index=True,
        width='stretch',
        column_config={
            "PredHomeWin": st.column_config.ProgressColumn(
                label="Home Win",
                min_value=0.0,
                max_value=1.0,
                format="%.0%",
            ),
            "PredDraw": st.column_config.ProgressColumn(
                label="Draw",
                min_value=0.0,
                max_value=1.0,
                format="%.0%",
            ),
            "PredAwayWin": st.column_config.ProgressColumn(
                label="Away Win",
                min_value=0.0,
                max_value=1.0,
                format="%.0%",
            ),
        },
    )


# Usage:
# render_predictions_with_progress_bars(display_df)
```

---

## Quick Wins Checklist

| # | Feature | Time | Status |
|---|---|---|---|
| 1 | Match commentary generator | 5 min | ✅ Implemented in `utils.generate_match_commentary()` and `pages/predictions_tab.py` |
| 2 | Color-coded confidence rows | 3 min | ✅ Implemented with `utils.color_risk_rows()` |
| 3 | CSV download button | 2 min | ✅ Implemented on Predictions and Raw Data |
| 4 | Last-updated timestamp | 2 min | ✅ Implemented for fixtures and predictions |
| 5 | Team filter dropdown | 3 min | ✅ Implemented on Predictions, Markets, and Raw Data |
| 6 | Date range filter | 3 min | ✅ Implemented on Predictions |
| 7 | Feature importance chart | 5 min | ✅ Implemented on Statistics |
| 8 | Sidebar refresh button | 2 min | ⚪ Not implemented |
| 9 | Match countdown | 3 min | ✅ Implemented in sidebar |
| 10 | Progress bar columns | 5 min | ✅ Implemented in Predictions |
| | **Total** | **~33 min** | **9/10 complete** |
