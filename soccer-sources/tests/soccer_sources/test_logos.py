"""Test crest catalog mapping and caching without network access."""

import json
from pathlib import Path
from typing import Any

from soccer_sources.cli import app
from soccer_sources.leagues import get_league
from soccer_sources.logos import _catalog_directory, fetch_team_logos, load_team_logos, normalize_team_name
from typer.testing import CliRunner


def test_normalize_team_name_handles_accents_and_catalog_suffixes() -> None:
    assert normalize_team_name("Bayern München") == "bayern munich"
    assert normalize_team_name("TSG 1899 Hoffenheim") == "tsg 1899 hoffenheim"


def test_catalog_league_folders_cover_the_big_five() -> None:
    expected = {
        "bundesliga": "logos/Germany - Bundesliga",
        "premier-league": "logos/England - Premier League",
        "la-liga": "logos/Spain - LaLiga",
        "serie-a": "logos/Italy - Serie A",
        "ligue-1": "logos/France - Ligue 1",
    }

    assert {code: _catalog_directory(get_league(code), 2026) for code in expected} == expected


def test_provider_team_aliases_cover_names_returned_by_big_five_caches() -> None:
    aliases = {
        "Bayer Leverkusen": "Bayer 04 Leverkusen",
        "Freiburg": "SC Freiburg",
        "Paderborn": "SC Paderborn 07",
        "RasenBallsport Leipzig": "RB Leipzig",
        "Schalke 04": "FC Schalke 04",
        "Union Berlin": "1.FC Union Berlin",
        "Coventry": "Coventry City",
        "Everton": "Everton FC",
        "Fulham": "Fulham FC",
        "Hull": "Hull City",
        "Ipswich": "Ipswich Town",
        "Leeds": "Leeds United",
        "Celta Vigo": "Celta de Vigo",
        "Elche": "Elche CF",
        "Getafe": "Getafe CF",
        "Levante": "Levante UD",
        "Malaga": "Málaga CF",
        "Osasuna": "CA Osasuna",
        "Sevilla": "Sevilla FC",
        "Valencia": "Valencia CF",
        "Villarreal": "Villarreal CF",
        "Atalanta": "Atalanta BC",
        "Cagliari": "Cagliari Calcio",
        "Como": "Como 1907",
        "Frosinone": "Frosinone Calcio",
        "Genoa": "Genoa CFC",
        "Monza": "AC Monza",
        "Udinese": "Udinese Calcio",
        "Venezia": "Venezia FC",
        "Angers": "Angers SCO",
        "Le Havre": "Le Havre AC",
        "Le Mans": "Le Mans FC",
        "Lorient": "FC Lorient",
        "Monaco": "AS Monaco",
        "Nice": "OGC Nice",
        "Paris Saint Germain": "Paris Saint-Germain",
    }

    assert all(normalize_team_name(source) == normalize_team_name(catalog) for source, catalog in aliases.items())


def test_load_team_logos_is_cache_only(tmp_path: Path, monkeypatch: Any) -> None:
    logo_dir = tmp_path / "logos" / "bundesliga" / "2026"
    logo_dir.mkdir(parents=True)
    logo = logo_dir / "Bayern Munich.png"
    logo.write_bytes(b"png bytes")
    (logo_dir / "teams.json").write_text(json.dumps({"Bayern München": logo.name}), encoding="utf-8")

    def unexpected_request(*args: Any, **kwargs: Any) -> None:
        raise AssertionError("cache lookup must not access the network")

    monkeypatch.setattr("soccer_sources.logos.urlopen", unexpected_request)

    result = load_team_logos("bundesliga", 2026, cache_dir=tmp_path)

    assert result == {"Bayern München": logo}


def test_fetch_team_logos_downloads_known_alias_and_reports_unmatched(tmp_path: Path, monkeypatch: Any) -> None:
    directory = "Germany - Bundesliga"
    files = [
        {
            "name": "Bayern Munich.png",
            "download_url": (
                "https://raw.githubusercontent.com/luukhopman/football-logos/master/logos/"
                "Germany%20-%20Bundesliga/Bayern Munich.png"
            ),
        },
        {"name": "1.FC Köln.png"},
        {"name": "Borussia Dortmund.png"},
    ]
    calls: list[str] = []

    class Response:
        def __init__(self, body: bytes) -> None:
            self.body = body

        def __enter__(self) -> Response:
            return self

        def __exit__(self, *_: object) -> None:
            return None

        def read(self) -> bytes:
            return self.body

    def fake_urlopen(request: Any, timeout: float) -> Response:
        url = request.full_url
        calls.append(url)
        if url.endswith(directory.replace(" ", "%20")):
            return Response(json.dumps(files).encode())
        if url.endswith("Bayern%20Munich.png"):
            return Response(b"bayern png")
        raise AssertionError(f"Unexpected URL: {url}")

    monkeypatch.setattr("soccer_sources.logos.urlopen", fake_urlopen)

    result = fetch_team_logos(
        "bundesliga",
        2026,
        team_names=["Bayern München", "Unknown FC"],
        cache_dir=tmp_path,
    )

    assert list(result) == ["Bayern München"]
    assert result["Bayern München"].read_bytes() == b"bayern png"
    assert len(calls) == 2
    assert (tmp_path / "logos" / "bundesliga" / "2026" / "teams.json").exists()


def test_fetch_team_logos_uses_cached_mapping_without_refresh(tmp_path: Path, monkeypatch: Any) -> None:
    logo_dir = tmp_path / "logos" / "bundesliga" / "2026"
    logo_dir.mkdir(parents=True)
    logo = logo_dir / "Bayern Munich.png"
    logo.write_bytes(b"png bytes")
    (logo_dir / "teams.json").write_text(json.dumps({"Bayern München": logo.name}), encoding="utf-8")
    monkeypatch.setattr(
        "soccer_sources.logos.urlopen",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(AssertionError("network access")),
    )

    result = fetch_team_logos("bundesliga", 2026, team_names=["Bayern München"], cache_dir=tmp_path)

    assert result == {"Bayern München": logo}


def test_logos_cli_fetches_selected_league_and_season(monkeypatch: Any) -> None:
    calls: list[tuple[str, int, bool]] = []

    def fake_fetch(league: str, season: int, *, refresh: bool) -> dict[str, Path]:
        calls.append((league, season, refresh))
        return {"Bayern Munich": Path("bayern.png")}

    monkeypatch.setattr("soccer_sources.cli.fetch_team_logos", fake_fetch)
    result = CliRunner().invoke(app, ["logos", "--league", "bundesliga", "--season", "2026"])

    assert result.exit_code == 0
    assert "Cached 1 team crests" in result.stdout
    assert calls == [("bundesliga", 2026, False)]
