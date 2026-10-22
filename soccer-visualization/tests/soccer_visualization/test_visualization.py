"""Test plot builders with local Polars inputs."""

import base64
from typing import TYPE_CHECKING

import polars as pl
from soccer_visualization.xg import (
    multi_league_player_goals_vs_xg,
    multi_league_team_goals_vs_xg,
    multi_league_team_xg_for_against_per90,
    multi_league_xg_for_against_distribution,
    player_goals_vs_xg,
    shot_map,
    team_goals_vs_xg,
)

if TYPE_CHECKING:
    from pathlib import Path


def test_team_xg_figure_contains_regression_and_r_squared_without_one_to_one_line() -> None:
    stats = pl.DataFrame(
        {"team": ["Bayern Munich", "Borussia Dortmund", "Bayer Leverkusen"], "goals": [1, 3, 5], "xg": [1.0, 2.0, 3.0]}
    )

    figure = team_goals_vs_xg(stats, 2025)

    assert "Linear regression" in [trace.name for trace in figure.data]
    assert len(figure.layout.shapes) == 0
    trend = next(trace for trace in figure.data if trace.name == "Linear regression")
    assert list(trend.x) == [1.0, 3.0]
    assert list(trend.y) == [1.0, 5.0]
    assert "R² = 1.00" in figure.layout.title.text


def test_player_xg_figure_uses_team_colors_and_linear_regression() -> None:
    players = pl.DataFrame(
        {
            "player": ["Forward", "Winger", "Striker", "Madrid Forward"],
            "team": ["Bayern Munich", "Borussia Dortmund", "Bayer Leverkusen", "Real Madrid"],
            "goals": [1, 3, 5, 7],
            "xg": [1.0, 2.0, 3.0, 4.0],
        }
    )

    figure = player_goals_vs_xg(players, 2025)
    team_traces = {trace.name: trace for trace in figure.data if trace.name != "Linear regression"}

    assert team_traces["Bayern Munich"].marker.color == "#DC052D"
    assert team_traces["Bayern Munich"].marker.line.color == "#FFFFFF"
    assert team_traces["Borussia Dortmund"].marker.color == "#FDE100"
    assert team_traces["Borussia Dortmund"].marker.line.color == "#000000"
    assert team_traces["Real Madrid"].marker.color == "#FEBE10"
    assert team_traces["Real Madrid"].marker.line.color == "#FFFFFF"
    assert figure.layout.xaxis.range == figure.layout.yaxis.range
    assert figure.layout.yaxis.scaleanchor == "x"
    assert figure.layout.yaxis.scaleratio == 1
    assert figure.layout.width == figure.layout.height == 900
    assert "Linear regression" in [trace.name for trace in figure.data]
    assert "R² = 1.00" in figure.layout.title.text
    assert len(figure.layout.shapes) == 0


def test_shot_map_is_built() -> None:
    shots = pl.DataFrame(
        {"x": [0.5], "y": [0.3], "xg": [0.2], "minute": [4], "outcome": ["Saved"], "source_player_id": ["7"]}
    )

    map_figure = shot_map(shots)

    assert len(map_figure.data) == 1


def test_player_xg_figure_labels_ten_highest_xg_players() -> None:
    players = pl.DataFrame(
        {
            "player": [f"Player {rank}" for rank in range(12)],
            "team": ["Bayern Munich"] * 12,
            "goals": list(range(12)),
            "xg": list(map(float, range(12))),
        }
    )

    figure = player_goals_vs_xg(players, 2026)
    labels = next(trace for trace in figure.data if trace.name == "Top 10 players")

    assert list(labels.text) == [f"Player {rank}" for rank in range(11, 1, -1)]


def test_team_xg_figure_uses_crests_and_fallback_hover_markers(tmp_path: Path) -> None:
    stats = pl.DataFrame({"team": ["Team A", "Team B"], "goals": [2, 3], "xg": [1.5, 2.5]})
    crest = tmp_path / "team-a.png"
    crest.write_bytes(
        base64.b64decode("iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+/7h8AAAAASUVORK5CYII=")
    )

    figure = team_goals_vs_xg(stats, 2026, logo_paths={"Team A": crest})

    hover = next(trace for trace in figure.data if trace.name == "Team hover targets")
    fallback = next(trace for trace in figure.data if trace.name == "Missing crest fallback")
    assert len(figure.layout.images) == 1
    assert str(figure.layout.images[0].source).startswith("data:image/png;base64,")
    assert [row[0] for row in hover.customdata] == ["Team B", "Team A"]
    assert list(fallback.text) == ["Team B"]


def test_team_xg_figure_uses_fallback_for_invalid_crest_and_missing_goals(tmp_path: Path) -> None:
    stats = pl.DataFrame(
        {"team": ["Invalid logo", "Unknown goals"], "goals": [2.0, None], "xg": [1.5, 0.8]},
        schema={"team": pl.String, "goals": pl.Float64, "xg": pl.Float64},
    )
    invalid_crest = tmp_path / "invalid.png"
    invalid_crest.write_bytes(b"local png fixture")

    figure = team_goals_vs_xg(stats, 2026, logo_paths={"Invalid logo": invalid_crest})

    hover = next(trace for trace in figure.data if trace.name == "Team hover targets")
    fallback = next(trace for trace in figure.data if trace.name == "Missing crest fallback")
    assert list(hover.x) == [1.5]
    assert list(hover.y) == [2.0]
    assert list(fallback.text) == ["Invalid logo"]


def test_multi_league_team_figure_includes_league_hover_and_crests(tmp_path: Path) -> None:
    summary = pl.DataFrame(
        {
            "league": ["bundesliga", "premier-league", "serie-a"],
            "team": ["United", "United", "Roma"],
            "goals": [3.0, 5.0, 2.0],
            "xg": [2.0, 3.0, 2.5],
            "goals_minus_xg": [1.0, 2.0, -0.5],
            "provenance": ["team_match", "player_season_fallback", "team_match"],
        }
    )
    logos = {}
    for key in [("bundesliga", "United"), ("premier-league", "United")]:
        path = tmp_path / f"{key[0]}.png"
        path.write_bytes(
            base64.b64decode(
                "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+/7h8AAAAASUVORK5CYII="
            )
        )
        logos[key] = path

    figure = multi_league_team_goals_vs_xg(summary, 2026, logo_paths=logos)

    hover = next(trace for trace in figure.data if trace.name == "Team hover targets")
    assert len(figure.layout.images) == 2
    assert "League:" in hover.hovertemplate
    assert "Goals - xG:" in hover.hovertemplate
    assert [row[1] for row in hover.customdata] == ["bundesliga", "premier-league", "serie-a"]
    assert len(figure.layout.shapes) == 0
    assert "R² =" in figure.layout.title.text


def test_multi_league_player_figure_shows_league_and_top_xg_scorers() -> None:
    players = pl.DataFrame(
        {
            "league": ["bundesliga", "bundesliga", "premier-league", "premier-league"],
            "player": ["Bayern Forward", "Dortmund Forward", "Arsenal Forward", "City Forward"],
            "team": ["Bayern Munich", "Borussia Dortmund", "Arsenal", "Manchester City"],
            "goals": [2, 4, 6, 8],
            "xg": [1.0, 2.0, 3.0, 4.0],
        }
    )

    figure = multi_league_player_goals_vs_xg(players, 2026)

    assert "Linear regression" in [trace.name for trace in figure.data]
    labels = next(trace for trace in figure.data if trace.name == "Top 10 players")
    assert "Big Five player goals vs xG" in figure.layout.title.text
    assert "R² = 1.00" in figure.layout.title.text
    marker = next(trace for trace in figure.data if trace.mode == "markers")
    assert "league" in marker.hovertemplate.lower()
    assert list(labels.text) == ["City Forward", "Arsenal Forward", "Dortmund Forward", "Bayern Forward"]
    assert len(figure.layout.shapes) == 0


def test_multi_league_player_labels_recalculate_for_selected_leagues() -> None:
    players = pl.DataFrame(
        {
            "league": ["bundesliga"] * 3 + ["premier-league"] * 12,
            "player": ["Bundesliga 1", "Bundesliga 2", "Bundesliga 3"] + [f"Premier {rank}" for rank in range(12)],
            "team": ["Bayern Munich"] * 3 + ["Arsenal"] * 12,
            "goals": list(range(15)),
            "xg": list(map(float, range(15))),
        }
    )

    selected_players = players.filter(pl.col("league").is_in(["bundesliga"]))
    figure = multi_league_player_goals_vs_xg(selected_players, 2026)
    labels = next(trace for trace in figure.data if trace.name == "Top 10 players")

    assert list(labels.text) == ["Bundesliga 3", "Bundesliga 2", "Bundesliga 1"]


def test_big_five_xg_for_against_plot_marks_four_quadrants(tmp_path: Path) -> None:
    summary = pl.DataFrame(
        {
            "league": ["bundesliga", "premier-league", "la-liga", "serie-a"],
            "team": ["Attack", "Leaky", "Defensive", "Low output"],
            "xg_for_per90": [2.0, 2.0, 0.5, 0.5],
            "xg_against_per90": [0.5, 2.0, 0.5, 2.0],
            "matches": [10, 10, 10, 10],
            "quadrant": [
                "High attack · strong defense",
                "High attack · leaky defense",
                "Low attack · strong defense",
                "Low attack · leaky defense",
            ],
        }
    )

    crest = tmp_path / "attack.png"
    crest.write_bytes(
        base64.b64decode("iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+/7h8AAAAASUVORK5CYII=")
    )
    figure = multi_league_team_xg_for_against_per90(
        summary,
        2026,
        logo_paths={("bundesliga", "Attack"): crest},
    )

    hover = next(trace for trace in figure.data if trace.name == "Team hover targets")
    assert [row[3] for row in hover.customdata] == summary["quadrant"].to_list()
    fallback = next(trace for trace in figure.data if trace.name == "Missing crest fallback")
    assert len(figure.layout.images) == 1
    assert list(fallback.text) == ["Leaky", "Defensive", "Low output"]
    assert sum(shape.type == "line" for shape in figure.layout.shapes) == 2
    assert sum(shape.type == "rect" for shape in figure.layout.shapes) == 4
    assert "Expected goals for per 90" in figure.layout.xaxis.title.text
    assert "Expected goals against per 90" in figure.layout.yaxis.title.text
    assert figure.layout.xaxis.range == figure.layout.yaxis.range
    assert figure.layout.yaxis.scaleanchor == "x"
    assert figure.layout.yaxis.scaleratio == 1
    assert figure.layout.width == figure.layout.height == 900
    assert {annotation.text for annotation in figure.layout.annotations} == set(summary["quadrant"].to_list())


def test_league_xg_for_against_distribution_shows_mean_and_one_sd_area() -> None:
    summary = pl.DataFrame(
        {
            "league": ["bundesliga", "premier-league"],
            "teams": [18, 20],
            "mean_xg_for_per90": [2.0, 1.8],
            "std_xg_for_per90": [1.0, 0.6],
            "mean_xg_against_per90": [1.0, 1.2],
            "std_xg_against_per90": [0.5, 0.4],
        }
    )

    figure = multi_league_xg_for_against_distribution(summary, 2026)

    means = {trace.name: trace for trace in figure.data}
    bundesliga_area = next(shape for shape in figure.layout.shapes if shape.name == "bundesliga ±1 SD")
    assert list(means["Bundesliga"].x) == [2.0]
    assert list(means["Bundesliga"].y) == [1.0]
    assert list(means) == ["Bundesliga", "Premier League"]
    assert (bundesliga_area.x0, bundesliga_area.x1) == (1.0, 3.0)
    assert (bundesliga_area.y0, bundesliga_area.y1) == (0.5, 1.5)
    assert figure.layout.xaxis.range == figure.layout.yaxis.range
    assert figure.layout.yaxis.scaleanchor == "x"
    assert "mean ± 1 SD" in figure.layout.title.text
