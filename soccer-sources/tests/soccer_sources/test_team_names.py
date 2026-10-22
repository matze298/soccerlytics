"""Tests for canonical team names and grouped aliases."""

from soccer_sources.team_names import TEAM_ALIASES, canonical_team_name


def test_team_aliases_are_grouped_by_canonical_name() -> None:
    assert TEAM_ALIASES["Bayern Munich"] == ("Bayern München", "FC Bayern München")
    assert canonical_team_name("Bayern München") == "Bayern Munich"
    assert canonical_team_name("St. Pauli") == "FC St. Pauli"
    assert canonical_team_name("1. FC Heidenheim 1846") == "1.FC Heidenheim 1846"
    assert canonical_team_name("Unlisted FC") == "Unlisted FC"
