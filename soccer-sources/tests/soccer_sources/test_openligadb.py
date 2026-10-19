"""Test OpenLigaDB response normalization without network access."""

from datetime import UTC, datetime
from pathlib import Path

import polars as pl
import pytest
from soccer_sources.cache import cache_file, write_parquet
from soccer_sources.leagues import get_league
from soccer_sources.openligadb import load_matches, parse_matches


def test_parse_matches_normalizes_ids_scores_and_utc_timestamps() -> None:
    payload = [
        {
            "matchID": 42,
            "matchDateTimeUTC": "2025-08-22T18:30:00Z",
            "matchIsFinished": True,
            "team1": {"teamId": 11, "teamName": "Bayern München"},
            "team2": {"teamId": 12, "teamName": "RB Leipzig"},
            "matchResults": [{"resultTypeID": 2, "pointsTeam1": 3, "pointsTeam2": 1, "resultName": "Endergebnis"}],
        }
    ]

    matches = parse_matches(payload, get_league("bundesliga"), 2025)

    assert matches.schema["kickoff_utc"] == pl.Datetime(time_zone="UTC")
    assert matches.row(0, named=True) == {
        "league": "bundesliga",
        "season": 2025,
        "source": "openligadb",
        "source_version": "openligadb-api-v1",
        "source_match_id": "42",
        "kickoff_utc": datetime(2025, 8, 22, 18, 30, tzinfo=UTC),
        "home_team_id": "11",
        "home_team_name": "Bayern München",
        "away_team_id": "12",
        "away_team_name": "RB Leipzig",
        "home_goals": 3,
        "away_goals": 1,
        "status": "finished",
        "source_url": "https://api.openligadb.de/getmatchdata/bl1/2025",
        "retrieved_at": None,
    }


def test_parse_matches_keeps_scores_missing_for_unplayed_matches() -> None:
    matches = parse_matches(
        [
            {
                "matchID": 43,
                "matchDateTimeUTC": "2025-08-29T18:30:00Z",
                "matchIsFinished": False,
                "team1": {"teamId": 11, "teamName": "Bayern München"},
                "team2": {"teamId": 12, "teamName": "RB Leipzig"},
                "matchResults": [],
            }
        ],
        get_league("bundesliga"),
        2025,
    )

    assert matches["home_goals"].item() is None
    assert matches["away_goals"].item() is None
    assert matches["status"].item() == "scheduled"


def test_duplicate_match_ids_are_rejected() -> None:
    payload = [
        {
            "matchID": 42,
            "matchDateTimeUTC": "2025-08-22T18:30:00Z",
            "team1": {},
            "team2": {},
        },
        {
            "matchID": 42,
            "matchDateTimeUTC": "2025-08-29T18:30:00Z",
            "team1": {},
            "team2": {},
        },
    ]

    with pytest.raises(ValueError, match="duplicate"):
        parse_matches(payload, get_league("bundesliga"), 2025)


def test_load_matches_reuses_parquet_cache(tmp_path: Path) -> None:
    cached = parse_matches([], get_league("bundesliga"), 2025)
    cache_path = cache_file("openligadb", "matches", "bundesliga", 2025, suffix="parquet", cache_dir=tmp_path)
    write_parquet(cached, cache_path)

    result = load_matches(cache_dir=str(tmp_path))

    assert result.is_empty()
