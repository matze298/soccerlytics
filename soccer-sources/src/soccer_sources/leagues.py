"""League identifiers shared by source adapters."""

from dataclasses import dataclass


@dataclass(frozen=True)
class League:
    """Stable league identity and provider-specific identifiers."""

    code: str
    name: str
    openligadb_code: str
    soccerdata_code: str

    def season_label(self, season: int) -> str:
        """Return a season label from its start year."""
        return f"{season}/{season + 1}"


_LEAGUES = {
    "bundesliga": League("bundesliga", "Bundesliga", "bl1", "GER-Bundesliga"),
    "premier-league": League("premier-league", "Premier League", "pl1", "ENG-Premier League"),
    "la-liga": League("la-liga", "La Liga", "la1", "ESP-La Liga"),
    "serie-a": League("serie-a", "Serie A", "it1", "ITA-Serie A"),
    "ligue-1": League("ligue-1", "Ligue 1", "fr1", "FRA-Ligue 1"),
}


def get_league(league: str | League) -> League:
    """Resolve a supported league code or pass through a League value."""
    if isinstance(league, League):
        return league
    try:
        return _LEAGUES[league.lower()]
    except KeyError as error:
        options = ", ".join(sorted(_LEAGUES))
        raise ValueError(f"Unsupported league {league!r}; choose from: {options}") from error
