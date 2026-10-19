"""Provider-independent schemas for normalized source tables."""

from datetime import UTC, datetime

import polars as pl

MATCH_SCHEMA: pl.Schema = pl.Schema(
    {
        "league": pl.String,
        "season": pl.Int16,
        "source": pl.String,
        "source_version": pl.String,
        "source_match_id": pl.String,
        "kickoff_utc": pl.Datetime(time_zone="UTC"),
        "home_team_id": pl.String,
        "home_team_name": pl.String,
        "away_team_id": pl.String,
        "away_team_name": pl.String,
        "home_goals": pl.Int16,
        "away_goals": pl.Int16,
        "status": pl.String,
        "source_url": pl.String,
        "retrieved_at": pl.Datetime(time_zone="UTC"),
    }
)

TEAM_MATCH_STATS_SCHEMA: pl.Schema = pl.Schema(
    {
        "league": pl.String,
        "season": pl.Int16,
        "source": pl.String,
        "source_version": pl.String,
        "source_match_id": pl.String,
        "source_team_id": pl.String,
        "team": pl.String,
        "goals": pl.Float64,
        "xg": pl.Float64,
        "xga": pl.Float64,
        "npxg": pl.Float64,
        "expected_points": pl.Float64,
        "source_url": pl.String,
        "retrieved_at": pl.Datetime(time_zone="UTC"),
    }
)

PLAYER_SEASON_STATS_SCHEMA: pl.Schema = pl.Schema(
    {
        "league": pl.String,
        "season": pl.Int16,
        "source": pl.String,
        "source_version": pl.String,
        "source_player_id": pl.String,
        "source_team_id": pl.String,
        "player": pl.String,
        "team": pl.String,
        "minutes": pl.Float64,
        "goals": pl.Float64,
        "xg": pl.Float64,
        "npxg": pl.Float64,
        "xa": pl.Float64,
        "source_url": pl.String,
        "retrieved_at": pl.Datetime(time_zone="UTC"),
    }
)

SHOTS_SCHEMA: pl.Schema = pl.Schema(
    {
        "league": pl.String,
        "season": pl.Int16,
        "source": pl.String,
        "source_version": pl.String,
        "source_shot_id": pl.String,
        "source_match_id": pl.String,
        "source_player_id": pl.String,
        "source_team_id": pl.String,
        "minute": pl.Int16,
        "x": pl.Float64,
        "y": pl.Float64,
        "outcome": pl.String,
        "xg": pl.Float64,
        "coordinate_system": pl.String,
        "source_url": pl.String,
        "retrieved_at": pl.Datetime(time_zone="UTC"),
    }
)


def utc_now() -> datetime:
    """Return a timezone-aware UTC timestamp for provenance."""
    return datetime.now(UTC)
