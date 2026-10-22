"""Explore cached Big Five and Bundesliga expected-goal tables."""

import marimo

app = marimo.App(width="full")
_SEASON_START_MONTH = 7


@app.cell
def _():
    import marimo as mo
    import polars as pl
    from soccer_analysis.xg import (
        league_xg_for_against_summary,
        multi_league_team_xg_summary,
        team_xg_for_against_per90,
        top_xg_scorers,
    )
    from soccer_sources.cache import DEFAULT_CACHE_DIR
    from soccer_sources.leagues import get_leagues
    from soccer_sources.season import load_season_data
    from soccer_visualization.xg import (
        multi_league_player_goals_vs_xg,
        multi_league_team_goals_vs_xg,
        multi_league_team_xg_for_against_per90,
        multi_league_xg_for_against_distribution,
        shot_map,
    )

    league_labels = {league.name: league.code for league in get_leagues()}
    league_codes = list(league_labels.values())
    cache_dir = DEFAULT_CACHE_DIR

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
        league_codes,
        league_labels,
        load_season_data,
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
                "Changing the season loads local caches and fetches missing source tables and the full season crest "
                "catalogs. Use this button to force a refresh of the selected season's data and crests."
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
    league_codes,
    load_season_data,
    mo,
    multi_league_team_xg_summary,
    pl,
    refresh_button,
    season_selector,
    team_xg_for_against_per90,
):
    _season = season_selector.value
    _data = load_season_data(
        league_codes,
        _season,
        match_leagues=["bundesliga"],
        refresh=bool(refresh_button.value),
        cache_dir=cache_dir,
    )
    all_player_stats = _data.player_season_stats
    openligadb_matches = _data.matches
    team_summary = multi_league_team_xg_summary(_data.team_match_stats, all_player_stats)
    team_xg_per90 = team_xg_for_against_per90(_data.team_match_stats)
    logos_by_league = _data.team_logos

    empty_team_stats = [
        _league for _league in league_codes if _data.team_match_stats.filter(pl.col("league") == _league).is_empty()
    ]
    available_player_leagues = set(all_player_stats.get_column("league").to_list())
    available_team_leagues = set(team_summary.get_column("league").to_list())
    missing_leagues = [
        _league
        for _league in league_codes
        if _league not in available_player_leagues and _league not in available_team_leagues
    ]
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
    if _data.errors:
        _notes.append("Some source data could not be loaded: " + " ".join(_data.errors))
    mo.md(" ".join(_notes))
    return all_player_stats, logos_by_league, openligadb_matches, team_summary, team_xg_per90


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
def _(mo):
    mo.md("## Bundesliga analysis")


@app.cell
def _(all_player_stats, league_xg_for_against_summary, logos_by_league, pl, team_summary, team_xg_per90):
    bundesliga_player_stats = all_player_stats.filter(pl.col("league") == "bundesliga")
    bundesliga_team_summary = team_summary.filter(pl.col("league") == "bundesliga")
    bundesliga_team_xg_per90 = team_xg_per90.filter(pl.col("league") == "bundesliga")
    bundesliga_xg_distribution = league_xg_for_against_summary(bundesliga_team_xg_per90)
    bundesliga_logos = {team: path for (league, team), path in logos_by_league.items() if league == "bundesliga"}
    return (
        bundesliga_logos,
        bundesliga_player_stats,
        bundesliga_team_summary,
        bundesliga_team_xg_per90,
        bundesliga_xg_distribution,
    )


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
        _shot_output = mo.md(f"Shot map omitted: there is no cached {_season}/{_season + 1} Understat shot table.")
    _shot_output


if __name__ == "__main__":
    app.run()
