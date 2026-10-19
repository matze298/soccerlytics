"""Test provider-independent xG summaries."""

import polars as pl
import pytest
from soccer_analysis.xg import (
    multi_league_team_xg_summary,
    player_goal_differences,
    team_xg_for_against_per90,
    team_xg_summary,
    top_xg_scorers,
)


def test_team_summary_compares_goals_and_xg_without_filling_missing_values() -> None:
    team_stats = pl.DataFrame(
        {
            "team": ["Bayern", "Bayern", "Mainz"],
            "goals": [2, 0, 1],
            "xg": [1.4, 0.2, None],
        }
    )

    summary = team_xg_summary(team_stats)

    assert summary["team"].to_list() == ["Bayern", "Mainz"]
    assert summary["goals"].to_list() == [2, 1]
    assert summary["xg"].to_list()[0] == pytest.approx(1.6)
    assert summary["goals_minus_xg"].to_list()[0] == pytest.approx(0.4)
    assert summary["xg"].to_list()[1] is None
    assert summary["goals_minus_xg"].to_list()[1] is None


def test_team_summary_preserves_all_null_goals() -> None:
    team_stats = pl.DataFrame(
        {"team": ["Unknown"], "goals": [None], "xg": [1.2]},
        schema={"team": pl.String, "goals": pl.Float64, "xg": pl.Float64},
    )

    summary = team_xg_summary(team_stats)

    assert summary["goals"].to_list() == [None]
    assert summary["goals_minus_xg"].to_list() == [None]


def test_player_goal_differences_uses_only_known_xg_values() -> None:
    players = pl.DataFrame({"player": ["A", "B"], "team": ["Bayern", "Mainz"], "goals": [10, 2], "xg": [8.5, None]})

    summary = player_goal_differences(players)

    assert summary["player"].to_list() == ["A", "B"]
    assert summary["goals_minus_xg"].to_list()[0] == pytest.approx(1.5)
    assert summary["goals_minus_xg"].to_list()[1] is None


def test_top_xg_scorers_returns_named_players_in_rank_order() -> None:
    players = pl.DataFrame(
        {
            "player": ["Low", "Top", "Unknown", "Middle"],
            "team": ["A", "B", "C", "D"],
            "goals": [1, 5, 9, 2],
            "xg": [0.5, 4.3, None, 2.7],
        }
    )

    top = top_xg_scorers(players, limit=2)

    assert top["player"].to_list() == ["Top", "Middle"]
    assert top["xg"].to_list() == [4.3, 2.7]


def test_multi_league_summary_prefers_team_rows_and_falls_back_per_league() -> None:
    team_rows = pl.DataFrame(
        {
            "league": ["bundesliga", "bundesliga"],
            "team": ["United", "United"],
            "goals": [2, 1],
            "xg": [1.5, 0.5],
        }
    )
    player_rows = pl.DataFrame(
        {
            "league": ["bundesliga", "premier-league", "premier-league"],
            "team": ["United", "United", "United"],
            "goals": [100, 3, 2],
            "xg": [99.0, 2.0, 1.0],
        }
    )

    summary = multi_league_team_xg_summary(team_rows, player_rows)

    bundesliga = summary.filter(pl.col("league") == "bundesliga").row(0, named=True)
    premier_league = summary.filter(pl.col("league") == "premier-league").row(0, named=True)
    assert bundesliga["team"] == "United"
    assert bundesliga["goals"] == 3.0
    assert bundesliga["xg"] == pytest.approx(2.0)
    assert bundesliga["provenance"] == "team_match"
    assert premier_league["goals"] == 5.0
    assert premier_league["xg"] == pytest.approx(3.0)
    assert premier_league["provenance"] == "player_season_fallback"
    assert summary.height == 2


def test_multi_league_summary_preserves_missing_xg_and_empty_inputs() -> None:
    team_rows = pl.DataFrame(
        {"league": ["bundesliga"], "team": ["Mainz"], "goals": [1.0], "xg": [None]},
        schema={"league": pl.String, "team": pl.String, "goals": pl.Float64, "xg": pl.Float64},
    )
    player_rows = pl.DataFrame(
        {"league": ["premier-league"], "team": ["Wolves"], "goals": [None], "xg": [None]},
        schema={"league": pl.String, "team": pl.String, "goals": pl.Float64, "xg": pl.Float64},
    )

    summary = multi_league_team_xg_summary(team_rows, player_rows)

    mainz = summary.filter(pl.col("team") == "Mainz").row(0, named=True)
    wolves = summary.filter(pl.col("team") == "Wolves").row(0, named=True)
    assert mainz["xg"] is None
    assert mainz["goals_minus_xg"] is None
    assert wolves["goals"] is None
    assert wolves["xg"] is None


def test_team_xg_for_against_summary_calculates_per90_and_global_quadrants() -> None:
    matches = pl.DataFrame(
        {
            "league": ["bundesliga", "bundesliga", "premier-league", "premier-league"],
            "team": ["Strong", "Strong", "Leaky", "Leaky"],
            "xg": [2.0, 2.0, 0.5, 0.5],
            "xga": [0.5, 0.5, 2.0, 2.0],
        }
    )

    summary = team_xg_for_against_per90(matches)

    strong = summary.filter(pl.col("team") == "Strong").row(0, named=True)
    leaky = summary.filter(pl.col("team") == "Leaky").row(0, named=True)
    assert strong["matches"] == 2
    assert strong["xg_for_per90"] == pytest.approx(2.0)
    assert strong["xg_against_per90"] == pytest.approx(0.5)
    assert strong["quadrant"] == "High attack · strong defense"
    assert leaky["quadrant"] == "Low attack · leaky defense"
