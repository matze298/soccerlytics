"""Load all source tables and crests used for a selected season."""

from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

import polars as pl

from soccer_sources.cache import DEFAULT_CACHE_DIR
from soccer_sources.leagues import League, get_league
from soccer_sources.logos import fetch_team_logos, load_team_logos
from soccer_sources.models import MATCH_SCHEMA, PLAYER_SEASON_STATS_SCHEMA, TEAM_MATCH_STATS_SCHEMA
from soccer_sources.openligadb import load_matches
from soccer_sources.understat import load_player_season_stats, load_team_match_stats

if TYPE_CHECKING:
    from collections.abc import Iterable


@dataclass(frozen=True)
class SeasonData:
    """Source tables and crests for the requested leagues and season."""

    matches: pl.DataFrame
    team_match_stats: pl.DataFrame
    player_season_stats: pl.DataFrame
    team_logos: dict[tuple[str, str], Path]
    errors: tuple[str, ...]


def load_season_data(
    leagues: Iterable[str | League],
    season: int,
    *,
    match_leagues: Iterable[str | League] | None = None,
    refresh: bool = False,
    cache_dir: str | Path = DEFAULT_CACHE_DIR,
) -> SeasonData:
    """Load source tables and the full crest catalog for each selected league.

    Returns:
        The loaded tables, crests keyed by ``(league, team)``, and provider errors.
    """
    root = Path(cache_dir)
    selected_leagues = tuple(get_league(league) for league in leagues)
    selected_match_leagues = (
        tuple(get_league(league) for league in match_leagues) if match_leagues is not None else selected_leagues
    )
    matches: list[pl.DataFrame] = []
    team_stats: list[pl.DataFrame] = []
    player_stats: list[pl.DataFrame] = []
    team_logos: dict[tuple[str, str], Path] = {}
    errors: list[str] = []

    for league in selected_match_leagues:
        try:
            matches.append(load_matches(league, season, refresh=refresh, cache_dir=str(root)))
        except Exception as error:  # ruff: ignore[blind-except] - Keep independent provider tables available after failures.
            matches.append(pl.DataFrame(schema=MATCH_SCHEMA))
            errors.append(f"{league.code}/OpenLigaDB matches: {error}")

    for league in selected_leagues:
        try:
            team_stats.append(load_team_match_stats(league, season, refresh=refresh, cache_dir=root))
        except Exception as error:  # ruff: ignore[blind-except] - Keep independent provider tables available after failures.
            team_stats.append(pl.DataFrame(schema=TEAM_MATCH_STATS_SCHEMA))
            errors.append(f"{league.code}/Understat team-match: {error}")

        try:
            player_stats.append(load_player_season_stats(league, season, refresh=refresh, cache_dir=root))
        except Exception as error:  # ruff: ignore[blind-except] - Keep independent provider tables available after failures.
            player_stats.append(pl.DataFrame(schema=PLAYER_SEASON_STATS_SCHEMA))
            errors.append(f"{league.code}/Understat player-season: {error}")

        try:
            fetch_team_logos(league, season, refresh=refresh, cache_dir=root)
        except Exception as error:  # ruff: ignore[blind-except] - Missing crests should not block xG analysis.
            errors.append(f"{league.code}/team crests: {error}")
        else:
            # The full catalog is keyed by catalog names. Resolve local files
            # again using source names so visualization lookups match stats.
            team_names = set()
            for table in (team_stats[-1], player_stats[-1]):
                if "team" in table.columns:
                    team_names.update(table.get_column("team").drop_nulls().unique().to_list())
            provider_logos = load_team_logos(league, season, team_names=team_names, cache_dir=root)
            team_logos.update({(league.code, name): path for name, path in provider_logos.items()})

    return SeasonData(
        matches=pl.concat(matches, how="diagonal_relaxed") if matches else pl.DataFrame(schema=MATCH_SCHEMA),
        team_match_stats=pl.concat(team_stats, how="diagonal_relaxed")
        if team_stats
        else pl.DataFrame(schema=TEAM_MATCH_STATS_SCHEMA),
        player_season_stats=pl.concat(player_stats, how="diagonal_relaxed")
        if player_stats
        else pl.DataFrame(schema=PLAYER_SEASON_STATS_SCHEMA),
        team_logos=team_logos,
        errors=tuple(errors),
    )
