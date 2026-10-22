"""Explore cached Big Five and Bundesliga expected-goal tables."""

import marimo

app = marimo.App(width="full")
_SEASON_START_MONTH = 7


@app.cell
def _():
    from pathlib import Path

    import marimo as mo
    import polars as pl
    from soccer_analysis.xg import (
        league_xg_for_against_summary,
        multi_league_team_xg_summary,
        team_xg_for_against_per90,
        top_xg_scorers,
    )
    from soccer_sources.cache import DEFAULT_CACHE_DIR
    from soccer_sources.logos import fetch_team_logos, load_team_logos
    from soccer_sources.openligadb import load_matches as load_openligadb_matches
    from soccer_sources.understat import load_player_season_stats, load_team_match_stats
    from soccer_visualization.xg import (
        multi_league_player_goals_vs_xg,
        multi_league_team_goals_vs_xg,
        multi_league_team_xg_for_against_per90,
        multi_league_xg_for_against_distribution,
        shot_map,
    )

    league_labels = {
        "Bundesliga": "bundesliga",
        "Premier League": "premier-league",
        "La Liga": "la-liga",
        "Serie A": "serie-a",
        "Ligue 1": "ligue-1",
    }
    league_codes = list(league_labels.values())
    cache_dir = Path(DEFAULT_CACHE_DIR)

    def make_league_selector(label):
        return mo.ui.multiselect(
            options=list(league_labels),
            value=list(league_labels),
            label=label,
            full_width=True,
        )

    mo.md("# Top Five Leagues and Bundesliga xG research")
    return (
        cache_dir,
        fetch_team_logos,
        league_codes,
        league_labels,
        load_team_logos,
        load_openligadb_matches,
        load_player_season_stats,
        load_team_match_stats,
        make_league_selector,
        mo,
        multi_league_player_goals_vs_xg,
        multi_league_team_goals_vs_xg,
        multi_league_team_xg_for_against_per90,
        multi_league_xg_for_against_distribution,
        multi_league_team_xg_summary,
        league_xg_for_against_summary,
        team_xg_for_against_per90,
        pl,
        shot_map,
        top_xg_scorers,
    )


@app.cell
def _(mo):
    refresh_button = mo.ui.run_button(label="Refresh cached data from providers")
    mo.vstack(
        [
            refresh_button,
            mo.md(
                "Changing the season loads local caches and fetches missing OpenLigaDB and Understat tables and team "
                "crests where available. Understat access is opt-in; selecting an uncached season authorizes that "
                "retrieval. Use this button to force a refresh of the selected season's data and crests. Read "
                "`docs/data-sources.md` before enabling "
                "Understat access."
            ),
        ]
    )
    return (refresh_button,)


@app.cell
def _(cache_dir, league_codes, mo):
    from datetime import UTC, datetime

    _season_dirs = [cache_dir / "understat" / _league for _league in league_codes]
    cached_seasons = {
        int(_path.name)
        for _directory in _season_dirs
        if _directory.exists()
        for _path in _directory.iterdir()
        if _path.is_dir() and _path.name.isdigit()
    }
    _today = datetime.now(UTC).date()
    _current_season = _today.year if _today.month >= _SEASON_START_MONTH else _today.year - 1
    available_seasons = sorted(
        {
            *range(2014, _current_season + 1),
            *cached_seasons,
        },
        reverse=True,
    )
    season_selector = mo.ui.dropdown(
        options=available_seasons,
        value=max(cached_seasons, default=available_seasons[0]),
        label="Season for all analyses (cached or available to fetch)",
    )
    mo.vstack(
        [
            season_selector,
            mo.md(
                "This season applies to both sections. Missing data is fetched when you select a season; the refresh "
                "button bypasses the cache."
            ),
        ]
    )
    return (season_selector,)


@app.cell
def _(
    cache_dir,
    fetch_team_logos,
    league_codes,
    load_openligadb_matches,
    load_player_season_stats,
    load_team_match_stats,
    mo,
    multi_league_team_xg_summary,
    pl,
    refresh_button,
    season_selector,
    team_xg_for_against_per90,
):
    _season = season_selector.value
    _refresh = bool(refresh_button.value)
    refresh_messages = []
    unavailable_tables = []
    unavailable_assets = []
    try:
        openligadb_matches = load_openligadb_matches(
            "bundesliga",
            _season,
            refresh=_refresh,
            cache_dir=str(cache_dir),
        )
    except Exception as _error:  # ruff: ignore[blind-except] - Keep independent tables available after provider failures.
        openligadb_matches = pl.DataFrame()
        unavailable_tables.append(f"OpenLigaDB matches: {_error}")

    team_frames = []
    player_frames = []
    missing_leagues = []
    empty_team_stats = []
    player_schema = {"league": pl.String, "team": pl.String, "player": pl.String, "goals": pl.Float64, "xg": pl.Float64}
    team_schema = {"league": pl.String, "team": pl.String, "goals": pl.Float64, "xg": pl.Float64}
    for _league_code in league_codes:
        _league_frames = []
        for _loader, _label, _schema in (
            (load_team_match_stats, "team-match", team_schema),
            (load_player_season_stats, "player-season", player_schema),
        ):
            try:
                _frame = _loader(
                    _league_code,
                    _season,
                    allow_scraping=True,
                    refresh=_refresh,
                    cache_dir=cache_dir,
                )
            except Exception as _error:  # ruff: ignore[blind-except] - Each league/table loads independently.
                _frame = pl.DataFrame(schema=_schema)
                unavailable_tables.append(f"{_league_code}/{_label}: {_error}")
            _league_frames.append(_frame)
            refresh_messages.append(f"{_league_code} {_label}: loaded {len(_frame)} rows.")
        _teams, _players = _league_frames
        team_frames.append(_teams if not _teams.is_empty() else pl.DataFrame(schema=team_schema))
        player_frames.append(_players if not _players.is_empty() else pl.DataFrame(schema=player_schema))
        if _teams.is_empty():
            empty_team_stats.append(_league_code)
        if _teams.is_empty() and _players.is_empty():
            missing_leagues.append(_league_code)

        _team_names = sorted(
            {
                str(_team)
                for _frame in _league_frames
                if "team" in _frame.columns
                for _team in _frame.get_column("team").drop_nulls().to_list()
            }
        )
        if _team_names:
            try:
                _logos = fetch_team_logos(
                    _league_code,
                    _season,
                    team_names=_team_names,
                    refresh=_refresh,
                    cache_dir=cache_dir,
                )
                if _refresh:
                    refresh_messages.append(f"{_league_code} crests: refreshed {len(_logos)}/{len(_team_names)}.")
            except Exception as _error:  # ruff: ignore[blind-except] - Missing crests should not block analysis.
                unavailable_assets.append(f"{_league_code} crests: {_error}")

    _all_teams = pl.concat(team_frames, how="diagonal_relaxed") if team_frames else pl.DataFrame(schema=team_schema)
    all_player_stats = (
        pl.concat(player_frames, how="diagonal_relaxed") if player_frames else pl.DataFrame(schema=player_schema)
    )
    team_summary = multi_league_team_xg_summary(_all_teams, all_player_stats)
    team_xg_per90 = team_xg_for_against_per90(_all_teams)
    fallback_leagues = (
        team_summary.filter(pl.col("provenance") == "player_season_fallback").get_column("league").unique().to_list()
        if not team_summary.is_empty()
        else []
    )
    _notes = []
    if missing_leagues:
        _notes.append(f"No xG data available for: {', '.join(missing_leagues)}.")
    if empty_team_stats:
        _notes.append(f"No team-match rows available for: {', '.join(empty_team_stats)}.")
    if fallback_leagues:
        _notes.append(
            f"Team totals are aggregated from Understat player-season rows for: {', '.join(fallback_leagues)}."
        )
    if not _notes:
        _notes.append("Team totals use Understat team-match rows where available.")
    if unavailable_tables:
        _notes.append("Some provider tables could not be loaded: " + " ".join(unavailable_tables))
    if unavailable_assets:
        _notes.append("Some team crests could not be loaded: " + " ".join(unavailable_assets))
    if refresh_messages and _refresh:
        _notes.append("Refresh results: " + " ".join(refresh_messages))
    mo.md(" ".join(_notes))
    return all_player_stats, openligadb_matches, team_summary, team_xg_per90


@app.cell
def _(mo):
    mo.md("## Big Five analysis")


@app.cell
def _(make_league_selector):
    big5_player_selector = make_league_selector("Leagues for player goals vs xG")
    return (big5_player_selector,)


@app.cell
def _(all_player_stats, big5_player_selector, league_labels, mo, multi_league_player_goals_vs_xg, pl, season_selector):
    _season = season_selector.value
    _leagues = [league_labels[_label] for _label in big5_player_selector.value]
    _players = all_player_stats.filter(pl.col("league").is_in(_leagues))
    big5_player_figure = (
        multi_league_player_goals_vs_xg(_players, _season)
        if not _players.is_empty()
        else mo.md("Player goals-versus-xG plot will appear after data is cached for selected leagues.")
    )
    mo.hstack([big5_player_selector, big5_player_figure], widths=[1, 4], align="center")


@app.cell
def _(make_league_selector):
    big5_team_selector = make_league_selector("Leagues for team goals vs xG")
    return (big5_team_selector,)


@app.cell
def _(
    big5_team_selector,
    league_labels,
    logos_by_league,
    mo,
    multi_league_team_goals_vs_xg,
    pl,
    season_selector,
    team_summary,
):
    _season = season_selector.value
    _leagues = [league_labels[_label] for _label in big5_team_selector.value]
    _teams = team_summary.filter(pl.col("league").is_in(_leagues))
    _logos = {key: path for key, path in logos_by_league.items() if key[0] in _leagues}
    big5_team_figure = (
        multi_league_team_goals_vs_xg(_teams, _season, logo_paths=_logos)
        if not _teams.is_empty()
        else mo.md("Team goals-versus-xG plot will appear after data is cached for selected leagues.")
    )
    mo.hstack([big5_team_selector, big5_team_figure], widths=[1, 4], align="center")


@app.cell
def _(make_league_selector):
    big5_quadrant_selector = make_league_selector("Leagues for team xG per 90")
    return (big5_quadrant_selector,)


@app.cell
def _(
    big5_quadrant_selector,
    league_labels,
    logos_by_league,
    mo,
    multi_league_team_xg_for_against_per90,
    pl,
    season_selector,
    team_xg_per90,
):
    _season = season_selector.value
    _leagues = [league_labels[_label] for _label in big5_quadrant_selector.value]
    _teams = team_xg_per90.filter(pl.col("league").is_in(_leagues))
    _logos = {key: path for key, path in logos_by_league.items() if key[0] in _leagues}
    big5_quadrant_figure = (
        multi_league_team_xg_for_against_per90(_teams, _season, logo_paths=_logos)
        if not _teams.is_empty()
        else mo.md("No team-match xG-for/against rows are cached for the selected leagues.")
    )
    mo.hstack([big5_quadrant_selector, big5_quadrant_figure], widths=[1, 4], align="center")


@app.cell
def _(make_league_selector):
    big5_distribution_selector = make_league_selector("Leagues for xG mean and spread")
    return (big5_distribution_selector,)


@app.cell
def _(
    big5_distribution_selector,
    league_labels,
    league_xg_for_against_summary,
    mo,
    multi_league_xg_for_against_distribution,
    pl,
    season_selector,
    team_xg_per90,
):
    _season = season_selector.value
    _leagues = [league_labels[_label] for _label in big5_distribution_selector.value]
    _teams = team_xg_per90.filter(pl.col("league").is_in(_leagues))
    _summary = league_xg_for_against_summary(_teams)
    big5_distribution_figure = (
        multi_league_xg_for_against_distribution(_summary, _season)
        if not _summary.is_empty()
        else mo.md("League means and spreads will appear after team xG-for/against rows are cached.")
    )
    mo.hstack([big5_distribution_selector, big5_distribution_figure], widths=[1, 4], align="center")


@app.cell
def _(make_league_selector):
    big5_scorer_selector = make_league_selector("Leagues for top xG scorers")
    return (big5_scorer_selector,)


@app.cell
def _(big5_scorer_selector, all_player_stats, league_labels, mo, pl, top_xg_scorers):
    _leagues = [league_labels[_label] for _label in big5_scorer_selector.value]
    _players = all_player_stats.filter(pl.col("league").is_in(_leagues))
    if _players.is_empty():
        _table = mo.md("Top xG scorers will appear after data is cached for selected leagues.")
    else:
        _scorers = (
            top_xg_scorers(_players)
            .select("player", "team", "goals", "xg")
            .with_row_index("rank", offset=1)
            .with_columns(pl.col("xg").round(2))
        )
        _table = mo.ui.table(_scorers)
    mo.hstack([big5_scorer_selector, mo.vstack([mo.md("### Top xG scorers (Understat)"), _table])], widths=[1, 4])


@app.cell
def _(cache_dir, league_codes, load_team_logos, pl, season_selector, team_summary):
    _season = season_selector.value
    logos_by_league = {}
    for _league_code in league_codes:
        _teams = (
            team_summary.filter(pl.col("league") == _league_code).get_column("team").drop_nulls().unique().to_list()
            if not team_summary.is_empty()
            else []
        )
        _league_logos = load_team_logos(
            _league_code,
            _season,
            team_names=_teams,
            cache_dir=cache_dir,
        )
        logos_by_league.update({(_league_code, _name): _path for _name, _path in _league_logos.items()})
    return (logos_by_league,)


@app.cell
def _(mo):
    mo.md("## Bundesliga analysis")


@app.cell
def _(all_player_stats, league_xg_for_against_summary, pl, team_summary, team_xg_per90):
    bundesliga_player_stats = all_player_stats.filter(pl.col("league") == "bundesliga")
    bundesliga_team_summary = team_summary.filter(pl.col("league") == "bundesliga")
    bundesliga_team_xg_per90 = team_xg_per90.filter(pl.col("league") == "bundesliga")
    bundesliga_xg_distribution = league_xg_for_against_summary(bundesliga_team_xg_per90)
    return bundesliga_player_stats, bundesliga_team_summary, bundesliga_team_xg_per90, bundesliga_xg_distribution


@app.cell
def _(bundesliga_player_stats, season_selector, mo, multi_league_player_goals_vs_xg):
    _season = season_selector.value
    bundesliga_player_figure = (
        multi_league_player_goals_vs_xg(bundesliga_player_stats, _season)
        if not bundesliga_player_stats.is_empty()
        else mo.md("Player goals-versus-xG plot will appear after Bundesliga data is cached for this season.")
    )
    bundesliga_player_figure


@app.cell
def _(
    season_selector,
    bundesliga_team_summary,
    bundesliga_logos,
    mo,
    multi_league_team_goals_vs_xg,
):
    _season = season_selector.value
    bundesliga_team_figure = (
        multi_league_team_goals_vs_xg(bundesliga_team_summary, _season, logo_paths=bundesliga_logos)
        if not bundesliga_team_summary.is_empty()
        else mo.md("Team goals-versus-xG plot will appear after Bundesliga data is cached for this season.")
    )
    bundesliga_team_figure


@app.cell
def _(
    season_selector,
    bundesliga_team_xg_per90,
    bundesliga_logos,
    mo,
    multi_league_team_xg_for_against_per90,
):
    _season = season_selector.value
    bundesliga_quadrant_figure = (
        multi_league_team_xg_for_against_per90(bundesliga_team_xg_per90, _season, logo_paths=bundesliga_logos)
        if not bundesliga_team_xg_per90.is_empty()
        else mo.md("No team-match xG-for/against rows are cached for this Bundesliga season.")
    )
    bundesliga_quadrant_figure


@app.cell
def _(
    season_selector,
    bundesliga_xg_distribution,
    mo,
    multi_league_xg_for_against_distribution,
):
    _season = season_selector.value
    bundesliga_distribution_figure = (
        multi_league_xg_for_against_distribution(bundesliga_xg_distribution, _season)
        if not bundesliga_xg_distribution.is_empty()
        else mo.md("Bundesliga mean and spread will appear after team xG-for/against rows are cached.")
    )
    bundesliga_distribution_figure


@app.cell
def _(bundesliga_player_stats, mo, pl, top_xg_scorers):
    if bundesliga_player_stats.is_empty():
        _table = mo.md("Top Bundesliga xG scorers will appear after player data is cached.")
    else:
        _scorers = (
            top_xg_scorers(bundesliga_player_stats)
            .select("player", "team", "goals", "xg")
            .with_row_index("rank", offset=1)
            .with_columns(pl.col("xg").round(2))
        )
        _table = mo.ui.table(_scorers)
    mo.vstack([mo.md("### Top Bundesliga xG scorers (Understat)"), _table])


@app.cell
def _(season_selector, cache_dir, load_team_logos, bundesliga_team_summary):
    _season = season_selector.value
    _team_names = (
        bundesliga_team_summary.get_column("team").drop_nulls().unique().to_list()
        if not bundesliga_team_summary.is_empty()
        else []
    )
    bundesliga_logos = load_team_logos("bundesliga", _season, team_names=_team_names, cache_dir=cache_dir)
    return (bundesliga_logos,)


@app.cell
def _(openligadb_matches, mo, season_selector):
    _season = season_selector.value
    if not openligadb_matches.is_empty():
        _match_output = mo.vstack([mo.md("### OpenLigaDB fixtures and results"), mo.ui.table(openligadb_matches)])
    else:
        _match_output = mo.md(
            f"No OpenLigaDB matches are available for {_season}/{_season + 1}; see the provider status above."
        )
    _match_output


@app.cell
def _(season_selector, cache_dir, mo, pl, shot_map):
    _season = season_selector.value
    _shots_path = cache_dir / "understat" / "bundesliga" / str(_season) / "shots.parquet"
    if _shots_path.exists():
        _shots = pl.read_parquet(_shots_path)
        _shot_output = shot_map(_shots)
    else:
        _shot_output = mo.md(
            f"Shot map omitted: there is no cached {_season}/{_season + 1} Understat shot table. Review the access "
            "notes and ingestion command in `docs/data-sources.md`."
        )
    _shot_output


if __name__ == "__main__":
    app.run()
