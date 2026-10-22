"""Canonical names for clubs shared by source adapters and visualizations."""

import unicodedata

TEAM_ALIASES: dict[str, tuple[str, ...]] = {
    "1.FC Heidenheim 1846": ("1. FC Heidenheim 1846", "FC Heidenheim 1846", "Heidenheim"),
    "1.FC Köln": ("1. FC Köln", "FC Cologne"),
    "1.FC Union Berlin": ("1. FC Union Berlin", "Union Berlin"),
    "1.FSV Mainz 05": ("1. FSV Mainz 05", "Mainz 05"),
    "AC Milan": ("Milan",),
    "AC Monza": ("Monza",),
    "ACF Fiorentina": ("Fiorentina",),
    "AFC Bournemouth": ("Bournemouth",),
    "AJ Auxerre": ("Auxerre",),
    "AS Monaco": ("Monaco",),
    "AS Roma": ("Roma",),
    "Angers SCO": ("Angers",),
    "Arsenal FC": ("Arsenal",),
    "Atalanta BC": ("Atalanta",),
    "Athletic Bilbao": ("Athletic Club",),
    "Atlético de Madrid": ("Atletico Madrid",),
    "Bayer 04 Leverkusen": ("Bayer Leverkusen",),
    "Bayern Munich": ("Bayern München", "FC Bayern München"),
    "Bologna FC 1909": ("Bologna",),
    "Borussia Mönchengladbach": ("Borussia M.Gladbach",),
    "Brentford FC": ("Brentford",),
    "Brighton & Hove Albion": ("Brighton",),
    "CA Osasuna": ("Osasuna",),
    "Cagliari Calcio": ("Cagliari",),
    "Celta de Vigo": ("Celta Vigo",),
    "Chelsea FC": ("Chelsea",),
    "Como 1907": ("Como",),
    "Coventry City": ("Coventry",),
    "Deportivo A Coruña": ("Deportivo La Coruna",),
    "Deportivo Alavés": ("Alaves",),
    "ESTAC Troyes": ("Troyes",),
    "Elche CF": ("Elche",),
    "Everton FC": ("Everton",),
    "FC Augsburg": ("Augsburg",),
    "FC Barcelona": ("Barcelona",),
    "FC Lorient": ("Lorient",),
    "FC Schalke 04": ("Schalke 04",),
    "FC St. Pauli": ("St. Pauli",),
    "FC Toulouse": ("Toulouse",),
    "Frosinone Calcio": ("Frosinone",),
    "Fulham FC": ("Fulham",),
    "Genoa CFC": ("Genoa",),
    "Getafe CF": ("Getafe",),
    "Hull City": ("Hull",),
    "Inter Milan": ("Inter",),
    "Ipswich Town": ("Ipswich",),
    "Juventus FC": ("Juventus",),
    "LOSC Lille": ("Lille",),
    "Le Havre AC": ("Le Havre",),
    "Le Mans FC": ("Le Mans",),
    "Leeds United": ("Leeds",),
    "Levante UD": ("Levante",),
    "Liverpool FC": ("Liverpool",),
    "Manchester United": ("Manchester United FC",),
    "Málaga CF": ("Malaga",),
    "OGC Nice": ("Nice",),
    "Olympique Lyon": ("Lyon",),
    "Olympique Marseille": ("Marseille",),
    "Paris Saint-Germain": ("Paris SG", "Paris Saint Germain", "PSG"),
    "RB Leipzig": ("RasenBallsport Leipzig",),
    "RC Lens": ("Lens",),
    "RC Strasbourg Alsace": ("Strasbourg",),
    "RCD Espanyol Barcelona": ("Espanyol",),
    "Real Betis Balompié": ("Real Betis",),
    "SC Freiburg": ("Freiburg",),
    "SC Paderborn 07": ("Paderborn",),
    "SS Lazio": ("Lazio",),
    "SSC Napoli": ("Napoli",),
    "SV 07 Elversberg": ("Elversberg", "SV Elversberg"),
    "SV Werder Bremen": ("Werder Bremen",),
    "Sevilla FC": ("Sevilla",),
    "Stade Brestois 29": ("Brest",),
    "Stade Rennais FC": ("Rennes",),
    "Sunderland AFC": ("Sunderland",),
    "TSG 1899 Hoffenheim": ("Hoffenheim", "TSG Hoffenheim"),
    "Torino FC": ("Torino",),
    "Tottenham Hotspur": ("Tottenham",),
    "US Lecce": ("Lecce",),
    "US Sassuolo": ("Sassuolo",),
    "Udinese Calcio": ("Udinese",),
    "Valencia CF": ("Valencia",),
    "Venezia FC": ("Venezia",),
    "Villarreal CF": ("Villarreal",),
    "West Ham United": ("West Ham",),
    "Wolverhampton Wanderers": ("Wolves",),
}


def _normalize_spelling(name: str) -> str:
    return " ".join(unicodedata.normalize("NFKD", name).encode("ascii", "ignore").decode().casefold().split())


_CANONICAL_NAMES = {
    _normalize_spelling(name): canonical
    for canonical, aliases in TEAM_ALIASES.items()
    for name in (canonical, *aliases)
}


def canonical_team_name(name: str) -> str:
    """Return the shared catalog name for a known team, preserving unknown names."""
    return _CANONICAL_NAMES.get(_normalize_spelling(name), name)


def normalize_team_name(name: str) -> str:
    """Return a normalized canonical key suitable for matching team names."""
    return _normalize_spelling(canonical_team_name(name))
