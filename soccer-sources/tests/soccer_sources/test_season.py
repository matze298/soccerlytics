"""Tests for loading a season's source tables and league crests."""

from __future__ import annotations

import json
from typing import TYPE_CHECKING

import polars as pl
from soccer_sources.season import load_season_data

if TYPE_CHECKING:
    from pathlib import Path

    import pytest
    from soccer_sources.leagues import League


def test_load_season_data_fetches_full_roster_and_maps_provider_team_names(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    logo_calls: list[tuple[str, int, bool, Path]] = []

    def empty_matches(*_args: object, **_kwargs: object) -> pl.DataFrame:
        return pl.DataFrame()

    def team_stats(*_args: object, **_kwargs: object) -> pl.DataFrame:
        return pl.DataFrame({"team": ["St. Pauli"]})

    def empty_player_stats(*_args: object, **_kwargs: object) -> pl.DataFrame:
        return pl.DataFrame()

    def fetch_logos(league: League, season: int, *, refresh: bool, cache_dir: Path) -> dict[str, Path]:
        logo_calls.append((league.code, season, refresh, cache_dir))
        logo_dir = cache_dir / "logos" / league.code / str(season)
        logo_dir.mkdir(parents=True)
        logo_path = logo_dir / "FC St. Pauli.png"
        logo_path.touch()
        (logo_dir / "teams.json").write_text(json.dumps({"FC St. Pauli": logo_path.name}), encoding="utf-8")
        return {"FC St. Pauli": logo_path}

    monkeypatch.setattr("soccer_sources.season.load_matches", empty_matches)
    monkeypatch.setattr("soccer_sources.season.load_team_match_stats", team_stats)
    monkeypatch.setattr("soccer_sources.season.load_player_season_stats", empty_player_stats)
    monkeypatch.setattr("soccer_sources.season.fetch_team_logos", fetch_logos)

    data = load_season_data(["bundesliga"], 2025, cache_dir=tmp_path)

    assert logo_calls == [
        (
            "bundesliga",
            2025,
            False,
            tmp_path,
        )
    ]
    assert data.team_logos == {
        ("bundesliga", "St. Pauli"): tmp_path / "logos" / "bundesliga" / "2025" / "FC St. Pauli.png"
    }
    assert data.team_match_stats.get_column("team").to_list() == ["St. Pauli"]
    assert not data.player_season_stats.height
