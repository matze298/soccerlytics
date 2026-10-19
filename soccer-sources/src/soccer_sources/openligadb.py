"""Fixtures and results from the public OpenLigaDB JSON API."""

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

import polars as pl

from soccer_sources.cache import DEFAULT_CACHE_DIR, cache_file, read_json, read_parquet, write_json, write_parquet
from soccer_sources.leagues import League, get_league
from soccer_sources.models import MATCH_SCHEMA

_BASE_URL = "https://api.openligadb.de"


def _utc_datetime(value: str) -> datetime:
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    return parsed.astimezone(UTC)


def parse_matches(
    payload: list[dict[str, Any]],
    league: League,
    season: int,
    *,
    retrieved_at: datetime | None = None,
) -> pl.DataFrame:
    """Normalize OpenLigaDB match records to the shared Polars match schema."""
    rows = []
    source_url = f"{_BASE_URL}/getmatchdata/{league.openligadb_code}/{season}"
    for match in payload:
        match_id = match.get("matchID")
        if match_id is None:
            raise ValueError("OpenLigaDB match is missing matchID")
        home, away = match.get("team1", {}), match.get("team2", {})
        results = match.get("matchResults", [])
        final = next(
            (result for result in reversed(results) if result.get("resultTypeID") == 2),
            results[-1] if results else None,
        )
        finished = bool(match.get("matchIsFinished"))
        rows.append(
            {
                "league": league.code,
                "season": season,
                "source": "openligadb",
                "source_version": "openligadb-api-v1",
                "source_match_id": str(match_id),
                "kickoff_utc": _utc_datetime(match["matchDateTimeUTC"]),
                "home_team_id": str(home["teamId"]) if home.get("teamId") is not None else None,
                "home_team_name": home.get("teamName"),
                "away_team_id": str(away["teamId"]) if away.get("teamId") is not None else None,
                "away_team_name": away.get("teamName"),
                "home_goals": final.get("pointsTeam1") if final else None,
                "away_goals": final.get("pointsTeam2") if final else None,
                "status": "finished" if finished else "scheduled",
                "source_url": source_url,
                "retrieved_at": retrieved_at,
            }
        )
    frame = pl.DataFrame(rows, schema=MATCH_SCHEMA, orient="row")
    if frame["source_match_id"].n_unique() != frame.height:
        raise ValueError("OpenLigaDB response contains duplicate match IDs")
    return frame


def load_matches(
    league: str | League = "bundesliga",
    season: int = 2025,
    *,
    refresh: bool = False,
    cache_dir: str | None = None,
    timeout: float = 20,
) -> pl.DataFrame:
    """Load one season of OpenLigaDB matches, reusing local Parquet unless refreshed."""
    selected = get_league(league)
    root = DEFAULT_CACHE_DIR if cache_dir is None else Path(cache_dir)
    parquet_path = cache_file("openligadb", "matches", selected.code, season, suffix="parquet", cache_dir=root)
    cached = None if refresh else read_parquet(parquet_path)
    if cached is not None:
        return cached

    raw_path = cache_file("openligadb", "matches", selected.code, season, suffix="json", cache_dir=root)
    payload = None if refresh else read_json(raw_path)
    url = f"{_BASE_URL}/getmatchdata/{selected.openligadb_code}/{season}"
    if payload is None:
        request = Request(url, headers={"User-Agent": "soccerlytics/0.1 (research)"})
        try:
            with urlopen(request, timeout=timeout) as response:
                payload = json.load(response)
        except (HTTPError, URLError, TimeoutError) as error:
            raise RuntimeError(f"Could not retrieve OpenLigaDB matches from {url}: {error}") from error
        write_json(payload, raw_path)
    frame = parse_matches(payload, selected, season, retrieved_at=datetime.now(UTC))
    write_parquet(frame, parquet_path)
    return frame
