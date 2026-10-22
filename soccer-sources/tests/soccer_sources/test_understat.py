"""Test Understat normalization with local records."""

from datetime import UTC, datetime
from typing import TYPE_CHECKING

import polars as pl
from soccer_sources.cache import cache_file, write_parquet
from soccer_sources.leagues import get_league
from soccer_sources.understat import (
    load_team_match_stats,
    normalize_player_season_stats,
    normalize_team_match_stats,
)

if TYPE_CHECKING:
    from pathlib import Path

    import pytest


def test_normalize_team_stats_preserves_xg_and_unmapped_metrics() -> None:
    timestamp = datetime(2026, 10, 18, tzinfo=UTC)

    frame = normalize_team_match_stats(
        [{"game": 81, "team": "Bayern Munich", "goals": 3, "xG": 2.2, "npxG": 1.8, "ppda": 7.4}],
        get_league("bundesliga"),
        2025,
        timestamp,
    )

    assert frame.row(0, named=True)["source_match_id"] == "81"
    assert frame.row(0, named=True)["team"] == "Bayern Munich"
    assert frame.row(0, named=True)["xg"] == 2.2
    assert frame.row(0, named=True)["npxg"] == 1.8
    assert frame.row(0, named=True)["ppda"] == 7.4


def test_normalize_understat_wide_match_stats_into_team_for_and_against_rows() -> None:
    timestamp = datetime(2026, 10, 18, tzinfo=UTC)

    frame = normalize_team_match_stats(
        [
            {
                "game": 81,
                "home_team": "Bayern Munich",
                "away_team": "Mainz 05",
                "home_goals": 3,
                "away_goals": 1,
                "home_xg": 2.2,
                "away_xg": 0.8,
            }
        ],
        get_league("bundesliga"),
        2025,
        timestamp,
    )

    assert frame.select("team", "goals", "xg", "xga").to_dicts() == [
        {"team": "Bayern Munich", "goals": 3.0, "xg": 2.2, "xga": 0.8},
        {"team": "Mainz 05", "goals": 1.0, "xg": 0.8, "xga": 2.2},
    ]


def test_normalize_player_stats_keeps_missing_metrics_null() -> None:
    timestamp = datetime(2026, 10, 18, tzinfo=UTC)

    frame = normalize_player_season_stats(
        [{"player": "Forward", "team": "Bayern Munich", "goals": 5, "xG": 4.2, "xA": None}],
        get_league("bundesliga"),
        2025,
        timestamp,
    )

    assert frame.row(0, named=True)["source_player_id"] is None
    assert frame.row(0, named=True)["xg"] == 4.2
    assert frame.row(0, named=True)["xa"] is None


def test_understat_fetches_a_cache_miss(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    class Reader:
        @staticmethod
        def read_team_match_stats(*, force_cache: bool) -> list[dict[str, object]]:
            assert force_cache
            return [{"game": 81, "team": "Bayern", "goals": 3, "xg": 2.2, "xga": 0.8}]

    monkeypatch.setattr("soccer_sources.understat._reader", lambda *_args, **_kwargs: (Reader(), "1.9.1"))

    result = load_team_match_stats(cache_dir=tmp_path)

    assert result.select("team", "xg", "xga").to_dicts() == [{"team": "Bayern", "xg": 2.2, "xga": 0.8}]


def test_understat_reads_cached_table_without_fetching(tmp_path: Path) -> None:
    cached = normalize_team_match_stats(
        [{"game": 81, "team": "Bayern", "goals": 3, "xg": 2.2}],
        get_league("bundesliga"),
        2025,
        datetime(2026, 10, 18, tzinfo=UTC),
        "1.9.1",
    )
    write_parquet(
        cached,
        cache_file("understat", "team_match_stats", "bundesliga", 2025, suffix="parquet", cache_dir=tmp_path),
    )

    result = load_team_match_stats(cache_dir=tmp_path)

    assert result.row(0, named=True)["team"] == "Bayern"


def test_team_match_loader_rebuilds_legacy_cache_with_xga(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    legacy = pl.DataFrame(
        {"league": ["bundesliga"], "team": ["Bayern"], "goals": [3.0], "xg": [2.2]},
        schema={"league": pl.String, "team": pl.String, "goals": pl.Float64, "xg": pl.Float64},
    )
    write_parquet(
        legacy,
        cache_file("understat", "team_match_stats", "bundesliga", 2025, suffix="parquet", cache_dir=tmp_path),
    )

    class CachedReader:
        @staticmethod
        def read_team_match_stats(*, force_cache: bool) -> list[dict[str, object]]:
            assert force_cache
            return [
                {
                    "game": 81,
                    "home_team": "Bayern",
                    "away_team": "Mainz",
                    "home_goals": 3,
                    "away_goals": 1,
                    "home_xg": 2.2,
                    "away_xg": 0.8,
                }
            ]

    monkeypatch.setattr(
        "soccer_sources.understat._reader",
        lambda *_args, **_kwargs: (CachedReader(), "1.9.1"),
    )

    result = load_team_match_stats("bundesliga", 2025, cache_dir=tmp_path)

    assert result.height == 2
    assert result.get_column("xga").to_list() == [0.8, 2.2]
