"""Expected-goal comparisons that work with Polars tables."""

import polars as pl


def team_xg_summary(team_match_stats: pl.DataFrame) -> pl.DataFrame:
    """Aggregate team goals and expected goals while preserving missing xG.

    Returns:
        One row per team with summed goals, xG, and their difference.

    Raises:
        ValueError: If required columns are missing.
    """
    required = {"team", "goals", "xg"}
    missing = required.difference(team_match_stats.columns)
    if missing:
        msg = f"Team match statistics are missing columns: {', '.join(sorted(missing))}"
        raise ValueError(msg)
    return (
        team_match_stats.group_by("team")
        .agg(
            pl.when(pl.col("goals").count() > 0).then(pl.col("goals").sum()).otherwise(None).alias("goals"),
            pl.when(pl.col("xg").count() > 0).then(pl.col("xg").sum()).otherwise(None).alias("xg"),
        )
        .with_columns((pl.col("goals") - pl.col("xg")).alias("goals_minus_xg"))
        .sort("xg", descending=True, nulls_last=True)
    )


def player_goal_differences(player_stats: pl.DataFrame) -> pl.DataFrame:
    """Return player goals minus xG, ordered by xG with missing values last.

    Returns:
        Player, team, goals, xG, and goal-difference columns.

    Raises:
        ValueError: If required columns are missing.
    """
    required = {"player", "team", "goals", "xg"}
    missing = required.difference(player_stats.columns)
    if missing:
        msg = f"Player statistics are missing columns: {', '.join(sorted(missing))}"
        raise ValueError(msg)
    return (
        player_stats.select("player", "team", "goals", "xg")
        .with_columns((pl.col("goals") - pl.col("xg")).alias("goals_minus_xg"))
        .sort("xg", descending=True, nulls_last=True)
    )


def top_xg_scorers(player_stats: pl.DataFrame, limit: int = 10) -> pl.DataFrame:
    """Return players with the highest known xG, ordered from highest to lowest.

    Raises:
        ValueError: If ``limit`` is less than one or required player columns are missing.
    """
    if limit < 1:
        msg = "limit must be greater than zero"
        raise ValueError(msg)
    return player_goal_differences(player_stats).drop_nulls("xg").head(limit)


def multi_league_team_xg_summary(team_match_stats: pl.DataFrame, player_season_stats: pl.DataFrame) -> pl.DataFrame:
    """Aggregate team goals and xG per league, preferring team-match rows when available.

    Returns:
        One row per league and team, including the source used for its totals.

    Raises:
        ValueError: If a non-empty input is missing required columns.
    """
    schema = pl.Schema(
        {
            "league": pl.String,
            "team": pl.String,
            "goals": pl.Float64,
            "xg": pl.Float64,
            "goals_minus_xg": pl.Float64,
            "provenance": pl.String,
        }
    )
    required = {"league", "team", "goals", "xg"}
    for name, frame in (("team-match", team_match_stats), ("player-season", player_season_stats)):
        missing = required.difference(frame.columns)
        if frame.height and missing:
            msg = f"{name} statistics are missing columns: {', '.join(sorted(missing))}"
            raise ValueError(msg)
    if team_match_stats.is_empty() and player_season_stats.is_empty():
        return pl.DataFrame(schema=schema)

    league_values = (
        set(team_match_stats.get_column("league").drop_nulls().to_list())
        if "league" in team_match_stats.columns
        else set()
    )
    if "league" in player_season_stats.columns:
        league_values.update(player_season_stats.get_column("league").drop_nulls().to_list())

    summaries: list[pl.DataFrame] = []
    for league in sorted(league_values):
        team_rows = (
            team_match_stats.filter(pl.col("league") == league)
            if team_match_stats.height and "league" in team_match_stats.columns
            else pl.DataFrame()
        )
        player_rows = (
            player_season_stats.filter(pl.col("league") == league)
            if player_season_stats.height and "league" in player_season_stats.columns
            else pl.DataFrame()
        )
        use_team_rows = team_rows.height > 0 and (team_rows.get_column("xg").count() > 0 or player_rows.is_empty())
        source = team_rows if use_team_rows else player_rows
        provenance = "team_match" if use_team_rows else "player_season_fallback"
        if source.is_empty():
            continue
        summaries.append(
            source.group_by("team")
            .agg(
                pl.when(pl.col("goals").count() > 0).then(pl.col("goals").sum()).otherwise(None).alias("goals"),
                pl.when(pl.col("xg").count() > 0).then(pl.col("xg").sum()).otherwise(None).alias("xg"),
            )
            .with_columns(
                pl.lit(league).alias("league"),
                (pl.col("goals") - pl.col("xg")).alias("goals_minus_xg"),
                pl.lit(provenance).alias("provenance"),
            )
            .select(schema.names())
            .cast(schema)
        )
    if not summaries:
        return pl.DataFrame(schema=schema)
    return pl.concat(summaries, how="vertical").sort("league", "team")


def team_xg_for_against_per90(team_match_stats: pl.DataFrame) -> pl.DataFrame:
    """Aggregate team-match xG and xGA into per-90 rates and global quadrants.

    Returns:
        One row per team with per-90 rates and its quadrant classification.

    Raises:
        ValueError: If required columns are missing.
    """
    schema = pl.Schema(
        {
            "league": pl.String,
            "team": pl.String,
            "matches": pl.UInt32,
            "xg_for_per90": pl.Float64,
            "xg_against_per90": pl.Float64,
            "quadrant": pl.String,
        }
    )
    if team_match_stats.is_empty():
        return pl.DataFrame(schema=schema)

    required = {"league", "team", "xg", "xga"}
    missing = required.difference(team_match_stats.columns)
    if missing:
        msg = f"Team match statistics are missing columns: {', '.join(sorted(missing))}"
        raise ValueError(msg)

    summary = (
        team_match_stats.select("league", "team", "xg", "xga")
        .with_columns(pl.col("xg", "xga").cast(pl.Float64, strict=False))
        .drop_nulls(["xg", "xga"])
        .group_by("league", "team")
        .agg(
            pl.len().cast(pl.UInt32).alias("matches"),
            pl.col("xg").mean().alias("xg_for_per90"),
            pl.col("xga").mean().alias("xg_against_per90"),
        )
    )
    if summary.is_empty():
        return pl.DataFrame(schema=schema)

    league_averages = summary.select(
        pl.col("xg_for_per90").mean().alias("avg_xg_for"),
        pl.col("xg_against_per90").mean().alias("avg_xg_against"),
    ).row(0, named=True)
    avg_for = league_averages["avg_xg_for"]
    avg_against = league_averages["avg_xg_against"]
    return (
        summary.with_columns(
            pl.when((pl.col("xg_for_per90") >= avg_for) & (pl.col("xg_against_per90") < avg_against))
            .then(pl.lit("High attack · strong defense"))
            .when((pl.col("xg_for_per90") >= avg_for) & (pl.col("xg_against_per90") >= avg_against))
            .then(pl.lit("High attack · leaky defense"))
            .when((pl.col("xg_for_per90") < avg_for) & (pl.col("xg_against_per90") < avg_against))
            .then(pl.lit("Low attack · strong defense"))
            .otherwise(pl.lit("Low attack · leaky defense"))
            .alias("quadrant")
        )
        .select(schema.names())
        .cast(schema)
        .sort("league", "team")
    )


def league_xg_for_against_summary(team_summary: pl.DataFrame) -> pl.DataFrame:
    """Summarize each league's team-level xG-for/against mean and population spread.

    Returns:
        One row per league with means and population standard deviations.

    Raises:
        ValueError: If a non-empty input is missing required columns.
    """
    schema = pl.Schema(
        {
            "league": pl.String,
            "teams": pl.UInt32,
            "mean_xg_for_per90": pl.Float64,
            "std_xg_for_per90": pl.Float64,
            "mean_xg_against_per90": pl.Float64,
            "std_xg_against_per90": pl.Float64,
        }
    )
    if team_summary.is_empty():
        return pl.DataFrame(schema=schema)

    required = {"league", "team", "xg_for_per90", "xg_against_per90"}
    missing = required.difference(team_summary.columns)
    if missing:
        msg = f"Team xG summary is missing columns: {', '.join(sorted(missing))}"
        raise ValueError(msg)

    return (
        team_summary.select("league", "team", "xg_for_per90", "xg_against_per90")
        .with_columns(pl.col("xg_for_per90", "xg_against_per90").cast(pl.Float64, strict=False))
        .drop_nulls(["league", "team", "xg_for_per90", "xg_against_per90"])
        .group_by("league")
        .agg(
            pl.col("team").n_unique().cast(pl.UInt32).alias("teams"),
            pl.col("xg_for_per90").mean().alias("mean_xg_for_per90"),
            pl.col("xg_for_per90").std(ddof=0).alias("std_xg_for_per90"),
            pl.col("xg_against_per90").mean().alias("mean_xg_against_per90"),
            pl.col("xg_against_per90").std(ddof=0).alias("std_xg_against_per90"),
        )
        .select(schema.names())
        .cast(schema)
        .sort("league")
    )
