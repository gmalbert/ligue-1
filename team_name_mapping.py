"""Normalize team names from football-data.co.uk, football-data.org, and FBref
to the canonical names used in the historical data (football-data.co.uk short names).

The canonical form is the football-data.co.uk short name because that is what
combined_historical_data.csv contains and what the model was trained on.
All external sources (football-data.org API full names, FBref, ESPN) are
mapped back to those short names so team stats lookups succeed.
"""

# Maps source variant → football-data.co.uk canonical short name
LIGUE1_TEAM_MAP: dict[str, str] = {
    # ── football-data.org full names → co.uk short names ─────────────────
    "Paris Saint-Germain FC":        "Paris SG",
    "Paris Saint-Germain":           "Paris SG",
    "PSG":                           "Paris SG",
    "Olympique de Marseille":        "Marseille",
    "Olympique Marseille":           "Marseille",
    "Olympique lyonnais":            "Lyon",
    "Olympique Lyonnais":            "Lyon",
    "Lyonnais":                      "Lyon",
    "AS Monaco FC":                  "Monaco",
    "AS Monaco":                     "Monaco",
    "LOSC Lille":                    "Lille",
    "Lille OSC":                     "Lille",
    "OGC Nice":                      "Nice",
    "RC Lens":                       "Lens",
    "Stade Rennais FC":              "Rennes",
    "Stade Rennais":                 "Rennes",
    "Rennes":                        "Rennes",
    "FC Girondins de Bordeaux":      "Bordeaux",
    "Girondins de Bordeaux":         "Bordeaux",
    "Montpellier HSC":               "Montpellier",
    "Stade de Reims":                "Reims",
    "FC Nantes":                     "Nantes",
    "Toulouse FC":                   "Toulouse",
    "RC Strasbourg Alsace":          "Strasbourg",
    "Strasbourg Alsace":             "Strasbourg",
    "Stade Brestois 29":             "Brest",
    "Stade Brestois":                "Brest",
    "Angers SCO":                    "Angers",
    "FC Lorient":                    "Lorient",
    "AS Saint-Étienne":              "St Etienne",
    "AS Saint-Etienne":              "St Etienne",
    "Saint-Etienne":                 "St Etienne",
    "Le Havre AC":                   "Le Havre",
    "Clermont Foot 63":              "Clermont",
    "Clermont Foot":                 "Clermont",
    "FC Metz":                       "Metz",
    "AJ Auxerre":                    "Auxerre",
    "ESTAC de Troyes":               "Troyes",
    "Troyes":                        "Troyes",
    "FC Sochaux-Montbéliard":        "Sochaux",
    "Gazélec Ajaccio":               "Gazélec",
    "Paris SG":                      "Paris SG",
    "Marseille":                     "Marseille",
    "Lyon":                          "Lyon",
    "Monaco":                        "Monaco",
    "Lille":                         "Lille",
    "Nice":                          "Nice",
    "Lens":                          "Lens",
    "Rennes":                        "Rennes",
    "Bordeaux":                      "Bordeaux",
    "Montpellier":                    "Montpellier",
    "Reims":                         "Reims",
    "Nantes":                        "Nantes",
    "Toulouse":                      "Toulouse",
    "Strasbourg":                    "Strasbourg",
    "Brest":                         "Brest",
    "Angers":                        "Angers",
    "Lorient":                       "Lorient",
    "St Etienne":                    "St Etienne",
    "Le Havre":                      "Le Havre",
    "Clermont":                      "Clermont",
    "Metz":                          "Metz",
    "Auxerre":                       "Auxerre",
    "Troyes":                        "Troyes",
    "Sochaux":                       "Sochaux",
    "Gazélec":                       "Gazélec",
}


def normalize_team_name(name: str) -> str:
    """Return the canonical team name, or the original if not in the map."""
    if not isinstance(name, str):
        return str(name)
    return LIGUE1_TEAM_MAP.get(name.strip(), name.strip())


def normalize_dataframe_teams(
    df,
    home_col: str = "HomeTeam",
    away_col: str = "AwayTeam",
):
    """Apply normalize_team_name to both team columns in a DataFrame."""
    import pandas as pd
    df = df.copy()
    if home_col in df.columns:
        df[home_col] = df[home_col].map(normalize_team_name)
    if away_col in df.columns:
        df[away_col] = df[away_col].map(normalize_team_name)
    return df
