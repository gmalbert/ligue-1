"""Shared optional PitchAPI team analytics."""

from pitch_oracle_core import get_league_config
from pitch_oracle_core.ui.pitchapi_analytics import legacy_context, render_team_page

render_team_page(legacy_context(get_league_config('ligue1')))
