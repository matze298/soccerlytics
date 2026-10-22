"""Test crest catalog mapping and caching without network access."""

import json
from pathlib import Path
from typing import TYPE_CHECKING, Self

from soccer_sources.cli import app
from soccer_sources.leagues import get_league
from soccer_sources.logos import (
    _catalog_directory,  # ruff: ignore[import-private-name] - Test explicit provider folder mappings without network access.
    fetch_team_logos,
    load_team_logos,
    normalize_team_name,
)
from soccer_sources.team_names import TEAM_ALIASES
from typer.testing import CliRunner

if TYPE_CHECKING:
    from urllib.request import Request

    import pytest


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
    assert all(
        normalize_team_name(alias) == normalize_team_name(canonical)
        for canonical, aliases in TEAM_ALIASES.items()
        for alias in aliases
    )


def test_load_team_logos_is_cache_only(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    logo_dir = tmp_path / "logos" / "bundesliga" / "2026"
    logo_dir.mkdir(parents=True)
    logo = logo_dir / "Bayern Munich.png"
    logo.write_bytes(b"png bytes")
    (logo_dir / "teams.json").write_text(json.dumps({"Bayern München": logo.name}), encoding="utf-8")

    def unexpected_request(*_args: object, **_kwargs: object) -> None:
        msg = "cache lookup must not access the network"
        raise AssertionError(msg)

    monkeypatch.setattr("soccer_sources.logos.urlopen", unexpected_request)

    result = load_team_logos("bundesliga", 2026, cache_dir=tmp_path)

    assert result == {"Bayern München": logo}


def test_fetch_team_logos_downloads_known_alias_and_reports_unmatched(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
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

        def __enter__(self) -> Self:
            return self

        def __exit__(self, *_: object) -> None:
            return None

        def read(self) -> bytes:
            return self.body

    def fake_urlopen(request: Request, timeout: float) -> Response:
        assert timeout == 30
        url = request.full_url
        calls.append(url)
        if url.endswith(directory.replace(" ", "%20")):
            return Response(json.dumps(files).encode())
        if url.endswith("Bayern%20Munich.png"):
            return Response(b"bayern png")
        msg = f"Unexpected URL: {url}"
        raise AssertionError(msg)

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


def test_fetch_team_logos_resolves_heidenheim_and_st_pauli_in_2025_catalog(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    files = [
        {"name": "1.FC Heidenheim 1846.png", "download_url": "https://raw.githubusercontent.com/heidenheim.png"},
        {"name": "FC St. Pauli.png", "download_url": "https://raw.githubusercontent.com/st-pauli.png"},
    ]

    def fake_request(url: str) -> bytes:
        if "api.github.com" in url:
            return json.dumps(files).encode()
        return b"crest image"

    monkeypatch.setattr("soccer_sources.logos._request_bytes", fake_request)

    logos = fetch_team_logos("bundesliga", 2025, team_names=["Heidenheim", "St. Pauli"], cache_dir=tmp_path)

    assert set(logos) == {"Heidenheim", "St. Pauli"}
    assert {path.name for path in logos.values()} == {"1.FC Heidenheim 1846.png", "FC St. Pauli.png"}


def test_fetch_team_logos_downloads_full_la_liga_2025_roster(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    teams = [
        "Athletic Bilbao",
        "Atlético de Madrid",
        "CA Osasuna",
        "Celta de Vigo",
        "Deportivo Alavés",
        "Elche CF",
        "FC Barcelona",
        "Getafe CF",
        "Girona FC",
        "Levante UD",
        "RCD Espanyol Barcelona",
        "RCD Mallorca",
        "Rayo Vallecano",
        "Real Betis Balompié",
        "Real Madrid",
        "Real Oviedo",
        "Real Sociedad",
        "Sevilla FC",
        "Valencia CF",
        "Villarreal CF",
    ]
    entries = [
        {"name": f"{team}.png", "download_url": f"https://raw.githubusercontent.com/{team}.png"} for team in teams
    ]

    def fake_request(url: str) -> bytes:
        if "api.github.com" in url:
            return json.dumps(entries).encode()
        return b"crest image"

    monkeypatch.setattr("soccer_sources.logos._request_bytes", fake_request)

    logos = fetch_team_logos("la-liga", 2025, cache_dir=tmp_path)

    assert len(logos) == 20
    assert {path.stem for path in logos.values()} == set(teams)


def test_fetch_team_logos_uses_cached_mapping_without_refresh(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
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


def test_logos_cli_fetches_selected_league_and_season(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[tuple[str, int, bool]] = []

    def fake_fetch(league: str, season: int, *, refresh: bool) -> dict[str, Path]:
        calls.append((league, season, refresh))
        return {"Bayern Munich": Path("bayern.png")}

    monkeypatch.setattr("soccer_sources.cli.fetch_team_logos", fake_fetch)
    result = CliRunner().invoke(app, ["logos", "--league", "bundesliga", "--season", "2026"])

    assert result.exit_code == 0
    assert "Cached 1 team crests" in result.stdout
    assert calls == [("bundesliga", 2026, False)]
