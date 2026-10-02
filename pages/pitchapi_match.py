"""Shared optional PitchAPI match analytics."""

from pitch_oracle_core import get_league_config
from pitch_oracle_core.ui.pitchapi_analytics import legacy_context, render_match_page

render_match_page(legacy_context(get_league_config('ligue1')))
