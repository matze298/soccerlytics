"""Explicit download and cache access for club crests used in local plots."""

import json
import unicodedata
from pathlib import Path
from typing import TYPE_CHECKING
from urllib.error import HTTPError, URLError
from urllib.parse import quote, urlsplit, urlunsplit
from urllib.request import Request, urlopen

from soccer_sources.cache import DEFAULT_CACHE_DIR
from soccer_sources.leagues import League, get_league

if TYPE_CHECKING:
    from collections.abc import Iterable

_API_BASE = "https://api.github.com/repos/luukhopman/football-logos/contents"
_CURRENT_LOGO_SEASON = 2026
_LEAGUE_FOLDERS = {
    "bundesliga": "Germany - Bundesliga",
    "premier-league": "England - Premier League",
    "la-liga": "Spain - LaLiga",
    "serie-a": "Italy - Serie A",
    "ligue-1": "France - Ligue 1",
}
_TEAM_ALIASES = {
    "1. FC Köln": "1.FC Köln",
    "FC Cologne": "1.FC Köln",
    "1. FC Union Berlin": "1.FC Union Berlin",
    "1. FSV Mainz 05": "1.FSV Mainz 05",
    "Augsburg": "FC Augsburg",
    "Bayern München": "Bayern Munich",
    "Borussia M.Gladbach": "Borussia Mönchengladbach",
    "Elversberg": "SV 07 Elversberg",
    "Hoffenheim": "TSG 1899 Hoffenheim",
    "Mainz 05": "1.FSV Mainz 05",
    "Werder Bremen": "SV Werder Bremen",
    "Bayer Leverkusen": "Bayer 04 Leverkusen",
    "Freiburg": "SC Freiburg",
    "Paderborn": "SC Paderborn 07",
    "RasenBallsport Leipzig": "RB Leipzig",
    "Schalke 04": "FC Schalke 04",
    "Union Berlin": "1.FC Union Berlin",
    "Arsenal": "Arsenal FC",
    "Bournemouth": "AFC Bournemouth",
    "Brentford": "Brentford FC",
    "Brighton": "Brighton & Hove Albion",
    "Chelsea": "Chelsea FC",
    "Liverpool": "Liverpool FC",
    "Manchester United FC": "Manchester United",
    "Tottenham": "Tottenham Hotspur",
    "Sunderland": "Sunderland AFC",
    "West Ham": "West Ham United",
    "Wolves": "Wolverhampton Wanderers",
    "Coventry": "Coventry City",
    "Everton": "Everton FC",
    "Fulham": "Fulham FC",
    "Hull": "Hull City",
    "Ipswich": "Ipswich Town",
    "Leeds": "Leeds United",
    "Athletic Club": "Athletic Bilbao",
    "Alaves": "Deportivo Alavés",
    "Atletico Madrid": "Atlético de Madrid",
    "Barcelona": "FC Barcelona",
    "Espanyol": "RCD Espanyol Barcelona",
    "Real Betis": "Real Betis Balompié",
    "Celta Vigo": "Celta de Vigo",
    "Elche": "Elche CF",
    "Getafe": "Getafe CF",
    "Levante": "Levante UD",
    "Malaga": "Málaga CF",
    "Osasuna": "CA Osasuna",
    "Sevilla": "Sevilla FC",
    "Valencia": "Valencia CF",
    "Villarreal": "Villarreal CF",
    "Deportivo La Coruna": "Deportivo A Coruña",
    "Milan": "AC Milan",
    "Inter": "Inter Milan",
    "Fiorentina": "ACF Fiorentina",
    "Roma": "AS Roma",
    "Lazio": "SS Lazio",
    "Napoli": "SSC Napoli",
    "Juventus": "Juventus FC",
    "Bologna": "Bologna FC 1909",
    "Torino": "Torino FC",
    "Sassuolo": "US Sassuolo",
    "Lecce": "US Lecce",
    "Lyon": "Olympique Lyon",
    "Marseille": "Olympique Marseille",
    "Toulouse": "FC Toulouse",
    "Lille": "LOSC Lille",
    "Rennes": "Stade Rennais FC",
    "Brest": "Stade Brestois 29",
    "Strasbourg": "RC Strasbourg Alsace",
    "Lens": "RC Lens",
    "Auxerre": "AJ Auxerre",
    "Paris SG": "Paris Saint-Germain",
    "PSG": "Paris Saint-Germain",
    "Troyes": "ESTAC Troyes",
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
_ALIASES_BY_NORMALIZED = {
    " ".join(unicodedata.normalize("NFKD", alias).encode("ascii", "ignore").decode().casefold().split()): target
    for alias, target in _TEAM_ALIASES.items()
}


def normalize_team_name(name: str) -> str:
    """Normalize common accents and explicit provider/catalog aliases.

    Returns:
        A case-folded name suitable for matching provider names to catalog entries.
    """
    normalized = " ".join(unicodedata.normalize("NFKD", name).encode("ascii", "ignore").decode().casefold().split())
    target = _ALIASES_BY_NORMALIZED.get(normalized, name)
    return " ".join(unicodedata.normalize("NFKD", target).encode("ascii", "ignore").decode().casefold().split())


def _cache_directory(league: League, season: int, cache_dir: Path) -> Path:
    return cache_dir / "logos" / league.code / str(season)


def _load_manifest(directory: Path) -> dict[str, str]:
    path = directory / "teams.json"
    if not path.is_file():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except OSError, json.JSONDecodeError:
        return {}
    if not isinstance(data, dict):
        return {}
    return {str(name): str(filename) for name, filename in data.items() if isinstance(filename, str)}


def _manifest_paths(directory: Path, names: Iterable[str] | None) -> dict[str, Path]:
    manifest = _load_manifest(directory)
    by_normalized = {normalize_team_name(name): filename for name, filename in manifest.items()}
    requested = list(names) if names is not None else list(manifest)
    result: dict[str, Path] = {}
    for name in requested:
        filename = by_normalized.get(normalize_team_name(name))
        path = directory / filename if filename is not None else None
        if path is not None and path.is_file():
            result[name] = path
    return result


def load_team_logos(
    league: str | League,
    season: int,
    *,
    team_names: Iterable[str] | None = None,
    cache_dir: str | Path = DEFAULT_CACHE_DIR,
) -> dict[str, Path]:
    """Return cached crest paths only; this function never accesses the network.

    Returns:
        Paths for requested team crests that exist in the local cache.
    """
    selected = get_league(league)
    return _manifest_paths(_cache_directory(selected, season, Path(cache_dir)), team_names)


def _catalog_directory(league: League, season: int) -> str:
    try:
        league_folder = _LEAGUE_FOLDERS[league.code]
    except KeyError as error:
        msg = f"No crest catalog mapping exists for {league.code!r}"
        raise ValueError(msg) from error
    base = "logos" if season == _CURRENT_LOGO_SEASON else f"history/{season}-{str(season + 1)[-2:]}"
    return f"{base}/{league_folder}"


def _request_bytes(url: str) -> bytes:
    parts = urlsplit(url)
    if parts.scheme != "https" or parts.hostname not in {"api.github.com", "raw.githubusercontent.com"}:
        msg = "Crest catalog requests must use an approved HTTPS GitHub host"
        raise ValueError(msg)
    url = urlunsplit((parts.scheme, parts.netloc, quote(parts.path, safe="/%"), parts.query, parts.fragment))
    request = Request(url, headers={"Accept": "application/vnd.github+json", "User-Agent": "soccerlytics"})  # ruff: ignore[suspicious-url-open-usage] - URL host and scheme are validated above.
    try:
        with urlopen(request, timeout=30) as response:  # ruff: ignore[suspicious-url-open-usage] - URL host and scheme are validated above.
            body = response.read()
            if not isinstance(body, bytes):
                msg = "The logo catalog returned non-byte content"
                raise TypeError(msg)
            return body
    except (HTTPError, URLError, TimeoutError) as error:
        msg = f"Could not retrieve crest catalog resource {url}: {error}"
        raise RuntimeError(msg) from error


def fetch_team_logos(
    league: str | League,
    season: int,
    *,
    team_names: Iterable[str] | None = None,
    refresh: bool = False,
    cache_dir: str | Path = DEFAULT_CACHE_DIR,
) -> dict[str, Path]:
    """Fetch requested crests from the public catalog into the local cache.

    Returns:
        Paths for requested team crests that were found or downloaded.
    """
    selected = get_league(league)
    directory = _cache_directory(selected, season, Path(cache_dir))
    requested = list(team_names) if team_names is not None else None
    cached = {} if refresh else _manifest_paths(directory, requested)
    if requested is not None and len(cached) == len(requested):
        return cached

    catalog_path = _catalog_directory(selected, season)
    entries = json.loads(_request_bytes(f"{_API_BASE}/{quote(catalog_path, safe='/')}").decode("utf-8"))
    catalog = {
        normalize_team_name(Path(entry["name"]).stem): entry
        for entry in entries
        if isinstance(entry, dict) and str(entry.get("name", "")).lower().endswith(".png")
    }
    selected_names = (
        requested if requested is not None else [str(entry["name"]).removesuffix(".png") for entry in catalog.values()]
    )
    mapping = _load_manifest(directory) if not refresh else {}
    result = dict(cached)
    directory.mkdir(parents=True, exist_ok=True)
    for name in selected_names:
        if name in result:
            continue
        entry = catalog.get(normalize_team_name(name))
        if entry is None:
            continue
        filename = str(entry["name"])
        image_path = directory / filename
        if refresh or not image_path.is_file():
            download_url = str(entry.get("download_url") or "")
            if not download_url:
                download_url = f"https://raw.githubusercontent.com/luukhopman/football-logos/master/{catalog_path}/{quote(filename)}"
            image_path.write_bytes(_request_bytes(download_url))
        mapping[name] = filename
        result[name] = image_path
    (directory / "teams.json").write_text(json.dumps(mapping, ensure_ascii=False, indent=2), encoding="utf-8")
    return result
