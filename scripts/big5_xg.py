"""Explore cached Big Five results and expected-goal tables."""

import marimo

app = marimo.App(width="full")


@app.cell
def _():
    from pathlib import Path

    import marimo as mo
    import polars as pl
    from soccer_analysis.xg import multi_league_team_xg_summary, team_xg_for_against_per90, top_xg_scorers
    from soccer_sources.cache import DEFAULT_CACHE_DIR
    from soccer_sources.logos import fetch_team_logos, load_team_logos
    from soccer_sources.openligadb import load_matches as load_openligadb_matches
    from soccer_sources.understat import load_player_season_stats, load_team_match_stats
    from soccer_visualization.xg import (
        multi_league_player_goals_vs_xg,
        multi_league_team_goals_vs_xg,
        multi_league_team_xg_for_against_per90,
        player_goals_vs_xg,
        shot_map,
        team_goals_vs_xg,
    )

    league_codes = ["bundesliga", "premier-league", "la-liga", "serie-a", "ligue-1"]
    season = 2026
    cache_dir = Path(DEFAULT_CACHE_DIR)
    mo.md(f"# Big Five xG research · {season}/{season + 1}")
    return (
        cache_dir,
        fetch_team_logos,
        league_codes,
        load_team_logos,
        load_openligadb_matches,
        load_player_season_stats,
        load_team_match_stats,
        mo,
        multi_league_team_goals_vs_xg,
        multi_league_player_goals_vs_xg,
        multi_league_team_xg_summary,
        team_xg_for_against_per90,
        pl,
        player_goals_vs_xg,
        season,
        shot_map,
        team_goals_vs_xg,
        top_xg_scorers,
    )


@app.cell
def _(mo):
    refresh_button = mo.ui.run_button(label="Refresh cached data from providers")
    mo.vstack(
        [
            refresh_button,
            mo.md(
                "Refresh is manual and can take several minutes. It fetches OpenLigaDB fixtures/results, Understat "
                "team and player statistics, and team crests. Clicking the button acknowledges the opt-in Understat "
                "access described in `docs/data-sources.md`."
            ),
        ]
    )
    return (refresh_button,)


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
    season,
    team_xg_for_against_per90,
):
    refresh_messages = []
    if refresh_button.value:
        try:
            _matches = load_openligadb_matches("bundesliga", season, refresh=True, cache_dir=str(cache_dir))
            refresh_messages.append(f"OpenLigaDB: refreshed {len(_matches)} Bundesliga fixtures/results.")
        except Exception as _error:
            refresh_messages.append(f"OpenLigaDB refresh failed: {_error}")
        for _league_code in league_codes:
            _league_frames = []
            for _loader, _label in (
                (load_team_match_stats, "team-match"),
                (load_player_season_stats, "player-season"),
            ):
                try:
                    _frame = _loader(
                        _league_code,
                        season,
                        allow_scraping=True,
                        refresh=True,
                        cache_dir=cache_dir,
                    )
                    _league_frames.append(_frame)
                    refresh_messages.append(f"{_league_code} {_label}: refreshed {len(_frame)} rows.")
                except Exception as _error:
                    refresh_messages.append(f"{_league_code} {_label} refresh failed: {_error}")
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
                        season,
                        team_names=_team_names,
                        refresh=True,
                        cache_dir=cache_dir,
                    )
                    refresh_messages.append(f"{_league_code} crests: refreshed {len(_logos)}/{len(_team_names)}.")
                except Exception as _error:
                    refresh_messages.append(f"{_league_code} crest refresh failed: {_error}")
    team_frames = []
    player_frames = []
    missing_leagues = []
    missing_cache_tables = []
    empty_team_stats = []
    player_schema = {
        "league": pl.String,
        "team": pl.String,
        "player": pl.String,
        "goals": pl.Float64,
        "xg": pl.Float64,
    }
    team_schema = {"league": pl.String, "team": pl.String, "goals": pl.Float64, "xg": pl.Float64}
    for _league_code in league_codes:
        _base = cache_dir / "understat" / _league_code / str(season)
        _player_path = _base / "player_season_stats.parquet"
        _team_path = _base / "team_match_stats.parquet"
        if _player_path.exists():
            _players = pl.read_parquet(_player_path)
            player_frames.append(_players)
        else:
            _players = pl.DataFrame(schema=player_schema)
            missing_cache_tables.append(f"{_league_code}/player_season_stats.parquet")
        if _team_path.exists():
            _teams = pl.read_parquet(_team_path)
            team_frames.append(_teams if not _teams.is_empty() else pl.DataFrame(schema=team_schema))
            if _teams.is_empty():
                empty_team_stats.append(_league_code)
        else:
            _teams = pl.DataFrame(schema=team_schema)
            team_frames.append(pl.DataFrame(schema=team_schema))
            missing_cache_tables.append(f"{_league_code}/team_match_stats.parquet")
        if _players.is_empty() and _teams.is_empty():
            missing_leagues.append(_league_code)

    _all_teams = pl.concat(team_frames, how="diagonal_relaxed") if team_frames else pl.DataFrame(schema=team_schema)
    _all_players = (
        pl.concat(player_frames, how="diagonal_relaxed") if player_frames else pl.DataFrame(schema=player_schema)
    )
    team_summary = multi_league_team_xg_summary(_all_teams, _all_players)
    team_xg_per90 = team_xg_for_against_per90(_all_teams)
    player_stats = (
        _all_players.filter(pl.col("league") == "bundesliga")
        if not _all_players.is_empty()
        else pl.DataFrame(schema=player_schema)
    )
    all_player_stats = _all_players
    bundesliga_team_stats = team_summary.filter(pl.col("league") == "bundesliga").select("team", "goals", "xg")
    fallback_leagues = (
        team_summary.filter(pl.col("provenance") == "player_season_fallback").get_column("league").unique().to_list()
        if not team_summary.is_empty()
        else []
    )
    _notes = []
    if missing_cache_tables:
        _notes.append(f"Missing cached tables: {', '.join(missing_cache_tables)}.")
    if missing_leagues:
        _notes.append(f"No cached xG data: {', '.join(missing_leagues)}.")
    if empty_team_stats:
        _notes.append(f"No team-match rows in cache for: {', '.join(empty_team_stats)}.")
    if fallback_leagues:
        _notes.append(
            f"Team totals are aggregated from Understat player-season rows for: {', '.join(fallback_leagues)}."
        )
    if not _notes:
        _notes.append("Team totals use cached Understat team-match rows where available.")
    if refresh_messages:
        _notes.append("Refresh results: " + " ".join(refresh_messages))
    data_note = mo.md(" ".join(_notes))
    mo.vstack([data_note, mo.md("## Data availability")])
    return all_player_stats, bundesliga_team_stats, player_stats, team_summary, team_xg_per90


@app.cell
def _(mo):
    league_labels = {
        "Bundesliga": "bundesliga",
        "Premier League": "premier-league",
        "La Liga": "la-liga",
        "Serie A": "serie-a",
        "Ligue 1": "ligue-1",
    }
    league_selector = mo.ui.multiselect(
        options=list(league_labels),
        value=list(league_labels),
        label="Leagues included in Big Five plots",
        full_width=True,
    )
    mo.vstack([league_selector, mo.md("Select one or more leagues to filter all Big Five plots and the scorer table.")])
    return league_labels, league_selector


@app.cell
def _(all_player_stats, league_labels, league_selector, mo, pl, team_summary, team_xg_per90):
    selected_leagues = [league_labels[_label] for _label in league_selector.value]
    selected_team_summary = team_summary.filter(pl.col("league").is_in(selected_leagues))
    selected_team_xg_per90 = team_xg_per90.filter(pl.col("league").is_in(selected_leagues))
    selected_player_stats = all_player_stats.filter(pl.col("league").is_in(selected_leagues))
    mo.md(f"Big Five plots include: {', '.join(league_selector.value) or 'no leagues'}.")
    return selected_leagues, selected_player_stats, selected_team_summary, selected_team_xg_per90


@app.cell
def _(load_team_logos, mo, pl, season, selected_leagues, selected_team_summary):
    logos_by_league = {}
    missing_logos = []
    if not selected_team_summary.is_empty():
        for _league_code in selected_leagues:
            _teams = (
                selected_team_summary.filter(pl.col("league") == _league_code)
                .get_column("team")
                .drop_nulls()
                .unique()
                .to_list()
            )
            _league_logos = load_team_logos(_league_code, season, team_names=_teams)
            logos_by_league.update({(_league_code, _name): _path for _name, _path in _league_logos.items()})
            missing_logos.extend(f"{_league_code}: {_name}" for _name in _teams if _name not in _league_logos)
    mo.md(
        "Cached crests are used where available. "
        + (
            f"No cached crest for: {', '.join(missing_logos)}."
            if missing_logos
            else "No missing crests for available teams."
        )
    )
    return logos_by_league, missing_logos


@app.cell
def _(bundesliga_team_stats, logos_by_league, mo, season, team_goals_vs_xg):
    _bundesliga_logos = {team: path for (league, team), path in logos_by_league.items() if league == "bundesliga"}
    team_figure = (
        team_goals_vs_xg(bundesliga_team_stats, season, logo_paths=_bundesliga_logos)
        if not bundesliga_team_stats.is_empty()
        else mo.md("Bundesliga team xG chart will appear after real Understat data is cached.")
    )
    team_figure
    return (team_figure,)


@app.cell
def _(mo, player_goals_vs_xg, player_stats, season):
    player_figure = (
        player_goals_vs_xg(player_stats, season)
        if not player_stats.is_empty()
        else mo.md("Bundesliga player xG chart will appear after real Understat data is cached.")
    )
    player_figure
    return (player_figure,)


@app.cell
def _(mo, multi_league_player_goals_vs_xg, season, selected_player_stats):
    big_five_player_figure = (
        multi_league_player_goals_vs_xg(selected_player_stats, season)
        if not selected_player_stats.is_empty()
        else mo.md("Big Five player goals-versus-xG plot will appear after data is cached for selected leagues.")
    )
    big_five_player_figure
    return (big_five_player_figure,)


@app.cell
def _(logos_by_league, mo, multi_league_team_goals_vs_xg, season, selected_team_summary):
    big_five_figure = (
        multi_league_team_goals_vs_xg(selected_team_summary, season, logo_paths=logos_by_league)
        if not selected_team_summary.is_empty()
        else mo.md("Big Five team goals-versus-xG plot will appear after data is cached for selected leagues.")
    )
    big_five_figure
    return (big_five_figure,)


@app.cell
def _(logos_by_league, mo, multi_league_team_xg_for_against_per90, season, selected_team_xg_per90):
    big_five_xg_for_against_figure = (
        multi_league_team_xg_for_against_per90(selected_team_xg_per90, season, logo_paths=logos_by_league)
        if not selected_team_xg_per90.is_empty()
        else mo.md(
            "No cached team-match xG-for/against rows are available for selected leagues. Run the opt-in Understat "
            "ingestion command after reviewing `docs/data-sources.md`."
        )
    )
    big_five_xg_for_against_figure
    return (big_five_xg_for_against_figure,)


@app.cell
def _(mo, pl, selected_player_stats, top_xg_scorers):
    if selected_player_stats.is_empty():
        top_xg_output = mo.md("Top xG scorers will appear after data is cached for selected leagues.")
    else:
        top_xg_table = (
            top_xg_scorers(selected_player_stats)
            .select("player", "team", "goals", "xg")
            .with_row_index("rank", offset=1)
            .with_columns(pl.col("xg").round(2))
        )
        top_xg_output = mo.vstack(
            [mo.md("## Top xG scorers in selected leagues (Understat)"), mo.ui.table(top_xg_table)]
        )
    top_xg_output
    return


@app.cell
def _(cache_dir, mo, pl, season):
    matches_path = cache_dir / "openligadb" / "bundesliga" / str(season) / "matches.parquet"
    if matches_path.exists():
        matches = pl.read_parquet(matches_path)
        match_output = mo.vstack([mo.md("## OpenLigaDB fixtures and results"), mo.ui.table(matches)])
    else:
        match_output = mo.md(
            "No OpenLigaDB match table is cached for 2026/27 yet. Run "
            "`uv run soccer-data openligadb --league bundesliga --season 2026`."
        )
    match_output
    return


@app.cell
def _(cache_dir, mo, pl, season, shot_map):
    shots_path = cache_dir / "understat" / "bundesliga" / str(season) / "shots.parquet"
    if shots_path.exists():
        shots = pl.read_parquet(shots_path)
        shot_output = shot_map(shots)
    else:
        shot_output = mo.md(
            "Shot map omitted: there is no cached 2026/27 Understat shot table. Review the access notes and "
            "ingestion command in `docs/data-sources.md`."
        )
    shot_output
    return


if __name__ == "__main__":
    app.run()
