
**Calibration note:** PSG matches will dominate your model's high-confidence picks. Consider filtering or flagging these separately in your UI.

**Backtesting window:** 2014–15 through 2023–24 (10 seasons, ~3,800 games).

---

## Implementation Plan

3. **Update Project Files:**

   - Update the name in all other relevant files.

### Step 2: Modify Data Sources
1. **Update `football-data.org` API Calls:**
   Ensure the API calls point to Ligue 1 data.

2. **Update Understat Data Pull:**
   Update the `understatapi` calls to fetch Ligue 1 data.

3. **Update The Odds API Calls:**
   Ensure the API calls point to Ligue 1 betting markets.

### Step 3: Create Streamlit App


2. **Add Streamlit App Code:**
   ```python
   import streamlit as st
   import understatapi

   # Streamlit app setup
   st.title("Ligue Odds")

   # Data fetching
   client = understatapi.UnderstatClient()
   matches = client.league(league="Ligue_1").get_match_data(season="2023")
   team_stats = client.league(league="Ligue_1").get_team_data(season="2023")

   # Display data
   st.dataframe(matches)
   st.dataframe(team_stats)
   ```

### Step 4: Test and Deploy
1. **Test the Streamlit App:**
   ```bash
   streamlit run predictions.py
   ```

2. **Deploy on Heroku or Vercel:**
   Follow the deployment instructions for Streamlit apps on Heroku or Vercel.

### Step 5: Maintain and Update
1. **Regular Data Updates:**
   Ensure the data sources are regularly updated.

2. **Model Calibration:**
   Periodically recalibrate the models to adapt to changes in the league.

3. **User Feedback:**
   Collect and act on user feedback to improve the site.

---

## Build Priority

**Medium — add as part of the European leagues bundle, but not a standalone priority.** Ligue Odds is worth including for completeness and because the marginal cost is zero if you're already building the other four leagues. It should not be a standalone build — bundle it with La Liga, Bundesliga, and Serie A as a single "five major leagues" expansion. The PSG dominance issue limits its standalone value as a picks source.