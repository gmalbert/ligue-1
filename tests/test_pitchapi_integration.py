from pitch_oracle_core import get_league_config
from pitch_oracle_core.features.families import FeatureFamilyConfig


def test_optional_pitchapi_is_registered_and_unpromoted_without_evidence(tmp_path):
    configuration = get_league_config('ligue1')
    assert configuration.sources.pitchapi
    assert configuration.sources.pitchapi_league_id
    assert FeatureFamilyConfig.load(tmp_path / "absent.json", league_key='ligue1').enabled_families == ()
