"""Command-line ingestion entry points."""

from pathlib import Path

import typer

from soccer_sources.logos import fetch_team_logos
from soccer_sources.openligadb import load_matches
from soccer_sources.understat import load_player_season_stats, load_team_match_stats

app = typer.Typer(help="Download soccer source tables into the local Parquet cache.")


@app.command("openligadb")
def ingest_openligadb(
    league: str = typer.Option("bundesliga", help="League code, for example bundesliga."),
    season: int = typer.Option(2025, help="Season start year."),
    *,
    refresh: bool = typer.Option(default=False, help="Ignore the normalized cache and fetch again."),
) -> None:
    """Fetch public fixtures and results from OpenLigaDB."""
    matches = load_matches(league, season, refresh=refresh)
    typer.echo(f"Cached {matches.height} matches from OpenLigaDB for {league} {season}/{season + 1}.")


@app.command("understat")
def ingest_understat(
    league: str = typer.Option("bundesliga", help="soccerdata-compatible league code."),
    season: int = typer.Option(2025, help="Season start year."),
    *,
    refresh: bool = typer.Option(default=False, help="Ignore both normalized and provider caches."),
) -> None:
    """Fetch and cache Understat team and player metrics."""
    cache_dir = Path(".cache/soccer")
    teams = load_team_match_stats(league, season, refresh=refresh, cache_dir=cache_dir)
    players = load_player_season_stats(league, season, refresh=refresh, cache_dir=cache_dir)
    typer.echo(f"Cached {teams.height} team-match rows and {players.height} player rows from Understat.")


@app.command("logos")
def ingest_logos(
    league: str = typer.Option("bundesliga", help="Supported league code."),
    season: int = typer.Option(2026, help="Season start year."),
    *,
    refresh: bool = typer.Option(default=False, help="Fetch logos again even when the local cache has them."),
) -> None:
    """Download team crests from the football-logos catalog into the local cache."""
    logos = fetch_team_logos(league, season, refresh=refresh)
    typer.echo(f"Cached {len(logos)} team crests for {league} {season}/{season + 1}.")


if __name__ == "__main__":
    app()
