# Suggestions for Moving from La Liga to Ligue-1

1. **Update Data Files**:
   - Rename or update the historical data files in the `data_files` folder to include Ligue-1 data.
   - For example, rename `SP1_1516.csv` to `FR1_1516.csv` and update the content accordingly.

2. **Update Team Name Mapping**:
   - Update the `team_name_mapping.py` file to include Ligue-1 team names.
   - For example, add entries for Ligue-1 teams like "Paris Saint-Germain", "Lyon", "Marseille", etc.

3. **Update Fetch Scripts**:
   - Update `fetch_upcoming_fixtures.py`, `fetch_historical_csvs.py`, `fetch_odds.py`, and `fetch_weather_data.py` to pull data for Ligue-1 instead of La Liga.
   - For example, modify the URL or query to fetch Ligue-1 data.

4. **Update Documentation**:
   - Update the `README.md` and other relevant documentation files to reflect the changes.
   - For example, update the section that describes the supported leagues to include Ligue-1.

5. **Update Configuration Files**:
   - Update any configuration files, such as `.env.example`, to include the necessary settings for Ligue-1.

6. **Update Fetching Scripts**:
   - Update `fetch_fbref_xg.py` to pull data for Ligue-1.
   - Update `fetch_copa_fixtures.py` to pull data for Ligue-1 if needed.

### Implementation Steps

1. **Update Data Files**:
   - Rename the historical data files in the `data_files` folder to include Ligue-1 data.
   - Update the content of the renamed files to include Ligue-1 data.

2. **Update Team Name Mapping**:
   - Edit `team_name_mapping.py` to include Ligue-1 team names.

3. **Update Fetch Scripts**:
   - Edit `fetch_upcoming_fixtures.py`, `fetch_historical_csvs.py`, `fetch_odds.py`, and `fetch_weather_data.py` to pull Ligue-1 data.

4. **Update Documentation**:
   - Edit `README.md` and other relevant documentation files to reflect the changes.

5. **Update Configuration Files**:
   - Edit `.env.example` to include the necessary settings for Ligue-1.

6. **Update Fetching Scripts**:
   - Edit `fetch_fbref_xg.py` to pull data for Ligue-1.