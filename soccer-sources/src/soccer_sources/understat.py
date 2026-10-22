"""Understat access through the community ``soccerdata`` package."""

import os
from collections.abc import Callable, Mapping
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import polars as pl

from soccer_sources.cache import DEFAULT_CACHE_DIR, cache_file, read_parquet, write_parquet
from soccer_sources.leagues import League, get_league
from soccer_sources.models import MATCH_SCHEMA, PLAYER_SEASON_STATS_SCHEMA, SHOTS_SCHEMA, TEAM_MATCH_STATS_SCHEMA

_BASE_URL = "https://understat.com/"


def _plain_column(name: object) -> str:
    parts = name if isinstance(name, tuple) else (name,)
    return "_".join(str(part).strip().lower().replace(" ", "_") for part in parts if str(part).strip())


def _records(frame: object) -> list[dict[str, Any]]:
    """Flatten pandas indexes/columns at the adapter boundary.

    Returns:
        Rows with normalized string column names.

    Raises:
        TypeError: If the provider table cannot be converted to records.
    """
    reset_index = getattr(frame, "reset_index", None)
    if callable(reset_index):
        frame = reset_index()
    to_dict = getattr(frame, "to_dict", None)
    if callable(to_dict):
        values = to_dict(orient="records")
        return [{_plain_column(key): value for key, value in row.items()} for row in values]
    if isinstance(frame, list) and all(isinstance(row, Mapping) for row in frame):
        return [{_plain_column(key): value for key, value in row.items()} for row in frame]
    msg = "soccerdata returned an unsupported table type"
    raise TypeError(msg)


def _value(row: Mapping[str, Any], *names: str) -> Any:  # ruff: ignore[any-type] - Provider cells retain pandas-native value types.
    return next((row[name] for name in names if name in row and row[name] is not None), None)


def _to_frame(records: list[dict[str, Any]], schema: pl.Schema) -> pl.DataFrame:
    if not records:
        return pl.DataFrame(schema=schema)
    frame = pl.DataFrame(records, infer_schema_length=None)
    overrides = {key: dtype for key, dtype in schema.items() if key in frame.columns}
    return frame.with_columns(pl.col(name).cast(dtype, strict=False) for name, dtype in overrides.items())


def normalize_schedule(
    frame: object, league: League, season: int, retrieved_at: datetime, source_version: str = "soccerdata"
) -> pl.DataFrame:
    """Normalize Understat's schedule while retaining its match identifiers.

    Returns:
        A Polars table with the shared match schema.
    """
    rows = []
    for row in _records(frame):
        game_id = _value(row, "game_id", "match_id", "id", "game")
        if game_id is None:
            continue
        kickoff = _value(row, "date", "datetime", "kickoff", "kickoff_utc")
        if isinstance(kickoff, str):
            kickoff = datetime.fromisoformat(kickoff)
        if isinstance(kickoff, datetime) and kickoff.tzinfo is None:
            kickoff = kickoff.replace(tzinfo=UTC)
        home_goals = _value(row, "home_goals", "goals_home")
        away_goals = _value(row, "away_goals", "goals_away")
        rows.append(
            {
                "league": league.code,
                "season": season,
                "source": "understat",
                "source_version": source_version,
                "source_match_id": str(game_id),
                "kickoff_utc": kickoff,
                "home_team_id": _value(row, "home_team_id"),
                "home_team_name": _value(row, "home_team", "home_team_name"),
                "away_team_id": _value(row, "away_team_id"),
                "away_team_name": _value(row, "away_team", "away_team_name"),
                "home_goals": home_goals,
                "away_goals": away_goals,
                "status": "finished" if home_goals is not None and away_goals is not None else "scheduled",
                "source_url": _BASE_URL,
                "retrieved_at": retrieved_at,
            }
        )
    return _to_frame(rows, MATCH_SCHEMA)


def normalize_team_match_stats(
    frame: object, league: League, season: int, retrieved_at: datetime, source_version: str = "soccerdata"
) -> pl.DataFrame:
    """Normalize Understat wide match rows or team rows into one row per team-match.

    Returns:
        A Polars table with the shared team-match statistics schema.
    """
    rows = []
    for row in _records(frame):
        team = _value(row, "team", "team_name", "team_team")
        home_team = _value(row, "home_team", "home_team_name")
        away_team = _value(row, "away_team", "away_team_name")
        if team is None and home_team is not None and away_team is not None:
            home_xg = _value(row, "home_xg")
            away_xg = _value(row, "away_xg")
            for side, side_team, other_xg in (
                ("home", home_team, away_xg),
                ("away", away_team, home_xg),
            ):
                rows.append(
                    {
                        "league": league.code,
                        "season": season,
                        "source": "understat",
                        "source_version": source_version,
                        "source_match_id": _value(row, "game_id", "match_id", "game"),
                        "source_team_id": str(_value(row, f"{side}_team_id"))
                        if _value(row, f"{side}_team_id")
                        else None,
                        "team": str(side_team),
                        "goals": _value(row, f"{side}_goals"),
                        "xg": _value(row, f"{side}_xg"),
                        "xga": other_xg,
                        "npxg": _value(row, f"{side}_np_xg", f"{side}_npxg"),
                        "expected_points": _value(row, f"{side}_expected_points", f"{side}_xpts"),
                        "ppda": _value(row, f"{side}_ppda"),
                        "source_url": _BASE_URL,
                        "retrieved_at": retrieved_at,
                    }
                )
            continue
        if team is None:
            continue
        reserved = set(TEAM_MATCH_STATS_SCHEMA.names())
        rows.append(
            {
                **{name: value for name, value in row.items() if name not in reserved},
                "league": league.code,
                "season": season,
                "source": "understat",
                "source_version": source_version,
                "source_match_id": _value(row, "game_id", "match_id", "game"),
                "source_team_id": str(_value(row, "team_id")) if _value(row, "team_id") else None,
                "team": str(team),
                "goals": _value(row, "goals", "goals_scored"),
                "xg": _value(row, "xg", "expected_goals"),
                "xga": _value(row, "xga", "expected_goals_against"),
                "npxg": _value(row, "npxg", "np_xg", "non_penalty_xg"),
                "expected_points": _value(row, "xpts", "expected_points"),
                "source_url": _BASE_URL,
                "retrieved_at": retrieved_at,
            }
        )
    return _to_frame(rows, TEAM_MATCH_STATS_SCHEMA)


def normalize_player_season_stats(
    frame: object, league: League, season: int, retrieved_at: datetime, source_version: str = "soccerdata"
) -> pl.DataFrame:
    """Normalize Understat player season rows and retain extra source metrics.

    Returns:
        A Polars table with the shared player-season statistics schema.
    """
    rows = []
    for row in _records(frame):
        player = _value(row, "player", "player_name", "name")
        if player is None:
            continue
        reserved = set(PLAYER_SEASON_STATS_SCHEMA.names())
        rows.append(
            {
                **{name: value for name, value in row.items() if name not in reserved},
                "league": league.code,
                "season": season,
                "source": "understat",
                "source_version": source_version,
                "source_player_id": str(_value(row, "player_id", "id")) if _value(row, "player_id", "id") else None,
                "source_team_id": str(_value(row, "team_id")) if _value(row, "team_id") else None,
                "player": str(player),
                "team": _value(row, "team", "team_name"),
                "minutes": _value(row, "time", "minutes", "min"),
                "goals": _value(row, "goals", "goal"),
                "xg": _value(row, "xg"),
                "npxg": _value(row, "npxg", "np_xg"),
                "xa": _value(row, "xa", "x_a", "expected_assists"),
                "source_url": _BASE_URL,
                "retrieved_at": retrieved_at,
            }
        )
    return _to_frame(rows, PLAYER_SEASON_STATS_SCHEMA)


def normalize_shots(
    frame: object, league: League, season: int, retrieved_at: datetime, source_version: str = "soccerdata"
) -> pl.DataFrame:
    """Normalize Understat shot events with their provider-native coordinates.

    Returns:
        A Polars table with the shared shot-event schema.
    """
    rows = []
    for row in _records(frame):
        shot_id = _value(row, "shot_id", "id")
        rows.append(
            {
                "league": league.code,
                "season": season,
                "source": "understat",
                "source_version": source_version,
                "source_shot_id": str(shot_id) if shot_id is not None else None,
                "source_match_id": _value(row, "game_id", "match_id", "game"),
                "source_player_id": _value(row, "player_id"),
                "source_team_id": _value(row, "team_id"),
                "minute": _value(row, "minute", "time"),
                "x": _value(row, "x", "location_x"),
                "y": _value(row, "y", "location_y"),
                "outcome": _value(row, "result", "outcome", "shot_result"),
                "xg": _value(row, "xg"),
                "coordinate_system": "understat_native",
                "source_url": _BASE_URL,
                "retrieved_at": retrieved_at,
            }
        )
    return _to_frame(rows, SHOTS_SCHEMA)


def _reader(league: League, season: int, *, refresh: bool, cache_dir: Path) -> tuple[Any, str]:
    # soccerdata configures file logging at import time, so defer it until an uncached fetch is requested.
    os.environ.setdefault("SOCCERDATA_DIR", str(cache_dir / "understat" / "soccerdata"))
    import soccerdata  # ruff: ignore[import-outside-top-level] - Keep third-party logging setup out of package imports.

    reader = soccerdata.Understat(
        leagues=league.soccerdata_code,
        seasons=league.season_label(season),
        no_cache=refresh,
        data_dir=cache_dir / "understat" / "raw",
    )
    return reader, soccerdata.__version__


def _load_table(  # ruff: ignore[too-many-arguments] - Loader options preserve cache and provider behaviors per entity.
    entity: str,
    method: str,
    normalize: Callable[[object, League, int, datetime, str], pl.DataFrame],
    league: str | League,
    season: int,
    *,
    refresh: bool,
    cache_dir: Path,
    required_cache_columns: set[str] | None = None,
    force_provider_cache: bool = False,
) -> pl.DataFrame:
    selected = get_league(league)
    path = cache_file("understat", entity, selected.code, season, suffix="parquet", cache_dir=cache_dir)
    cached = None if refresh else read_parquet(path)
    if cached is not None and (required_cache_columns is None or required_cache_columns.issubset(cached.columns)):
        return cached
    reader, source_version = _reader(selected, season, refresh=refresh, cache_dir=cache_dir)
    method_reader = getattr(reader, method)
    raw = method_reader(force_cache=True) if force_provider_cache else method_reader()
    frame = normalize(raw, selected, season, datetime.now(UTC), source_version)
    write_parquet(frame, path)
    return frame


def load_matches(
    league: str | League = "bundesliga",
    season: int = 2025,
    *,
    refresh: bool = False,
    cache_dir: str | Path = DEFAULT_CACHE_DIR,
) -> pl.DataFrame:
    """Load and cache Understat schedule rows, fetching them when uncached.

    Returns:
        A Polars table with the shared match schema.
    """
    return _load_table(
        "matches",
        "read_schedule",
        normalize_schedule,
        league,
        season,
        refresh=refresh,
        cache_dir=Path(cache_dir),
    )


def load_team_match_stats(
    league: str | League = "bundesliga",
    season: int = 2025,
    *,
    refresh: bool = False,
    cache_dir: str | Path = DEFAULT_CACHE_DIR,
) -> pl.DataFrame:
    """Load team match metrics, including Understat xG, into Polars.

    Returns:
        A Polars table with team-match statistics.
    """
    return _load_table(
        "team_match_stats",
        "read_team_match_stats",
        normalize_team_match_stats,
        league,
        season,
        refresh=refresh,
        cache_dir=Path(cache_dir),
        required_cache_columns={"xga"},
        force_provider_cache=True,
    )


def load_player_season_stats(
    league: str | League = "bundesliga",
    season: int = 2025,
    *,
    refresh: bool = False,
    cache_dir: str | Path = DEFAULT_CACHE_DIR,
) -> pl.DataFrame:
    """Load player season xG and available attacking metrics into Polars.

    Returns:
        A Polars table with player-season statistics.
    """
    return _load_table(
        "player_season_stats",
        "read_player_season_stats",
        normalize_player_season_stats,
        league,
        season,
        refresh=refresh,
        cache_dir=Path(cache_dir),
    )


def load_shots(
    league: str | League = "bundesliga",
    season: int = 2025,
    *,
    refresh: bool = False,
    cache_dir: str | Path = DEFAULT_CACHE_DIR,
) -> pl.DataFrame:
    """Load and cache Understat shot events.

    Returns:
        A Polars table with provider-native shot-event coordinates.
    """
    return _load_table(
        "shots",
        "read_shot_events",
        normalize_shots,
        league,
        season,
        refresh=refresh,
        cache_dir=Path(cache_dir),
    )
