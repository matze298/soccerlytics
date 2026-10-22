"""Fixtures and results from the public OpenLigaDB JSON API."""

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, cast
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

import polars as pl

from soccer_sources.cache import (
    DEFAULT_CACHE_DIR,
    JsonValue,
    cache_file,
    read_json,
    read_parquet,
    write_json,
    write_parquet,
)
from soccer_sources.leagues import League, get_league
from soccer_sources.models import MATCH_SCHEMA

_BASE_URL = "https://api.openligadb.de"
_FINAL_RESULT_TYPE_ID = 2


def _utc_datetime(value: str) -> datetime:
    parsed = datetime.fromisoformat(value)
    return parsed.astimezone(UTC)


def parse_matches(
    payload: list[dict[str, Any]],
    league: League,
    season: int,
    *,
    retrieved_at: datetime | None = None,
) -> pl.DataFrame:
    """Normalize OpenLigaDB match records to the shared Polars match schema.

    Returns:
        A normalized row for each source match.

    Raises:
        ValueError: If a record has no match identifier or identifiers are duplicated.
    """
    rows = []
    source_url = f"{_BASE_URL}/getmatchdata/{league.openligadb_code}/{season}"
    for match in payload:
        match_id = match.get("matchID")
        if match_id is None:
            msg = "OpenLigaDB match is missing matchID"
            raise ValueError(msg)
        home, away = match.get("team1", {}), match.get("team2", {})
        results = match.get("matchResults", [])
        final = next(
            (result for result in reversed(results) if result.get("resultTypeID") == _FINAL_RESULT_TYPE_ID),
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
        msg = "OpenLigaDB response contains duplicate match IDs"
        raise ValueError(msg)
    return frame


def load_matches(
    league: str | League = "bundesliga",
    season: int = 2025,
    *,
    refresh: bool = False,
    cache_dir: str | None = None,
    timeout: float = 20,
) -> pl.DataFrame:
    """Load one season of OpenLigaDB matches, reusing local Parquet unless refreshed.

    Returns:
        The normalized season table.

    Raises:
        RuntimeError: If the provider request fails.
        ValueError: If the response is not a list of match records.
    """
    selected = get_league(league)
    root = DEFAULT_CACHE_DIR if cache_dir is None else Path(cache_dir)
    parquet_path = cache_file("openligadb", "matches", selected.code, season, suffix="parquet", cache_dir=root)
    cached = None if refresh else read_parquet(parquet_path)
    if cached is not None:
        return cached

    raw_path = cache_file("openligadb", "matches", selected.code, season, suffix="json", cache_dir=root)
    payload: JsonValue | None = None if refresh else read_json(raw_path)
    url = f"{_BASE_URL}/getmatchdata/{selected.openligadb_code}/{season}"
    if payload is None:
        request = Request(url, headers={"User-Agent": "soccerlytics/0.1 (research)"})  # ruff: ignore[suspicious-url-open-usage] - URL uses the fixed HTTPS API base.
        try:
            with urlopen(request, timeout=timeout) as response:  # ruff: ignore[suspicious-url-open-usage] - URL uses the fixed HTTPS API base.
                payload = json.load(response)
        except (HTTPError, URLError, TimeoutError) as error:
            msg = f"Could not retrieve OpenLigaDB matches from {url}: {error}"
            raise RuntimeError(msg) from error
        write_json(payload, raw_path)
    if not isinstance(payload, list) or not all(isinstance(match, dict) for match in payload):
        msg = "OpenLigaDB returned a response that is not a list of match records"
        raise ValueError(msg)
    frame = parse_matches(cast("list[dict[str, Any]]", payload), selected, season, retrieved_at=datetime.now(UTC))
    write_parquet(frame, parquet_path)
    return frame
