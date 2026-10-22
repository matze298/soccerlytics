"""Plotly figures for team and player expected-goal analysis."""

import base64
from typing import TYPE_CHECKING, cast

import plotly.express as px
import plotly.graph_objects as go
import polars as pl
from soccer_analysis.xg import team_xg_summary

from soccer_visualization.colors import LEAGUE_COLORS, team_marker_colors

if TYPE_CHECKING:
    from collections.abc import Mapping
    from pathlib import Path

_MIN_REGRESSION_POINTS = 2


def _add_linear_regression(figure: go.Figure, data: pl.DataFrame) -> float | None:
    """Add an ordinary least-squares goals-on-xG line and return its R-squared.

    Returns:
        The coefficient of determination, or ``None`` when a line cannot be fit.
    """
    points = data.select("xg", "goals").drop_nulls().rows()
    if len(points) < _MIN_REGRESSION_POINTS:
        return None

    x_values, y_values = zip(*points, strict=True)
    x_mean = sum(x_values) / len(x_values)
    y_mean = sum(y_values) / len(y_values)
    x_variance = sum((value - x_mean) ** 2 for value in x_values)
    y_variance = sum((value - y_mean) ** 2 for value in y_values)
    if x_variance == 0 or y_variance == 0:
        return None

    slope = sum((x - x_mean) * (y - y_mean) for x, y in points) / x_variance
    intercept = y_mean - slope * x_mean
    residual_sum_squares = sum((y - (slope * x + intercept)) ** 2 for x, y in points)
    r_squared = 1 - residual_sum_squares / y_variance
    x_min, x_max = min(x_values), max(x_values)
    figure.add_trace(
        go.Scatter(
            x=[x_min, x_max],
            y=[slope * x_min + intercept, slope * x_max + intercept],
            mode="lines",
            name="Linear regression",
            line={"color": "#333333", "dash": "dash", "width": 2},
            hoverinfo="skip",
        )
    )
    return float(r_squared)


def _set_r_squared_title(figure: go.Figure, title: str, r_squared: float | None) -> None:
    suffix = f"R² = {r_squared:.2f}" if r_squared is not None else "R² = N/A"
    figure.update_layout(title=f"{title} ({suffix})")


def _set_equal_xy_scale(figure: go.Figure, data: pl.DataFrame, x_column: str, y_column: str) -> None:
    """Use the same numeric range and unit scale on both axes in a square figure."""
    values = [
        float(value) for column in (x_column, y_column) for value in data.get_column(column).drop_nulls().to_list()
    ]
    if values:
        lower = min(0.0, *values)
        upper = max(0.0, *values)
        padding = (upper - lower) * 0.08
        lower -= padding if lower < 0 else 0.0
        upper += padding
    else:
        lower, upper = 0.0, 1.0
    if lower == upper:
        upper = lower + 1.0

    figure.update_layout(width=900, height=900)
    figure.update_xaxes(range=[lower, upper], constrain="domain")
    figure.update_yaxes(range=[lower, upper], scaleanchor="x", scaleratio=1, constrain="domain")


def _set_player_marker_borders(figure: go.Figure) -> None:
    for trace in figure.data:
        if isinstance(trace, go.Scatter) and trace.mode == "markers":
            trace.marker.line = {
                "color": team_marker_colors(str(trace.name))[1],
                "width": 1.5,
            }


def _player_scatter(
    stats: pl.DataFrame,
    *,
    title: str,
    xg_label: str,
    league_detail: bool,
    label_limit: int,
) -> go.Figure:
    required = {"player", "team", "goals", "xg"}
    if league_detail:
        required.add("league")
    missing = required.difference(stats.columns)
    if missing:
        msg = f"Player statistics are missing columns: {', '.join(sorted(missing))}"
        raise ValueError(msg)
    if label_limit < 0:
        msg = "label_limit must be zero or greater"
        raise ValueError(msg)

    columns = ["player", "team", "goals", "xg"]
    if league_detail:
        columns.insert(0, "league")
    summary = (
        stats.select(columns)
        .with_columns((pl.col("goals") - pl.col("xg")).alias("goals_minus_xg"))
        .drop_nulls(["goals", "xg"])
    )
    team_colors = {team: team_marker_colors(team)[0] for team in summary.get_column("team").unique().to_list()}
    hover_data = {"goals_minus_xg": ":.2f"}
    if league_detail:
        hover_data["league"] = True
    figure = px.scatter(
        summary,
        x="xg",
        y="goals",
        color="team",
        color_discrete_map=team_colors,
        hover_name="player",
        hover_data=hover_data,
        labels={"xg": xg_label, "goals": "Actual goals"},
        title=title,
    )
    _set_player_marker_borders(figure)
    if label_limit:
        leaders = summary.sort("xg", descending=True).head(label_limit)
        figure.add_trace(
            go.Scatter(
                x=leaders.get_column("xg").to_list(),
                y=leaders.get_column("goals").to_list(),
                text=leaders.get_column("player").to_list(),
                mode="text",
                textposition="top center",
                name="Top 10 players",
                hoverinfo="skip",
                showlegend=False,
            )
        )
    r_squared = _add_linear_regression(figure, summary)
    _set_r_squared_title(figure, title, r_squared)
    _set_equal_xy_scale(figure, summary, "xg", "goals")
    return figure


def _logo_source(path: Path | None) -> str | None:
    if path is None or not path.is_file():
        return None
    try:
        content = path.read_bytes()
    except OSError:
        return None
    if not content.startswith(b"\x89PNG\r\n\x1a\n") or content[-8:-4] != b"IEND":
        return None
    encoded = base64.b64encode(content).decode("ascii")
    return f"data:image/png;base64,{encoded}"


def _add_team_markers(
    figure: go.Figure,
    summary: pl.DataFrame,
    logo_paths: Mapping[str, Path] | Mapping[tuple[str, str], Path],
    *,
    league_column: str | None = None,
) -> None:
    missing: list[dict[str, object]] = []
    missing_colors: list[str] = []
    hover_rows: list[list[object]] = []
    colors: list[str] = []
    for row in summary.iter_rows(named=True):
        team = str(row["team"])
        league = str(row[league_column]) if league_column else None
        key: str | tuple[str, str] = (league, team) if league is not None else team
        path = logo_paths.get(key)  # type: ignore[arg-type]
        source = _logo_source(path)
        color = team_marker_colors(team)[0]
        if league is not None:
            color = LEAGUE_COLORS.get(league, color)
        colors.append(color)
        if source is None:
            missing.append(row)
            missing_colors.append(color)
        else:
            figure.add_layout_image(
                source=source,
                x=float(row["xg"]),
                y=float(row["goals"]),
                xref="x",
                yref="y",
                xanchor="center",
                yanchor="middle",
                sizex=2.0,
                sizey=2.0,
                sizing="contain",
                layer="above",
            )
        custom = [team, row.get("league"), row.get("goals_minus_xg")]
        hover_rows.append(custom)

    figure.add_trace(
        go.Scatter(
            x=summary.get_column("xg").to_list(),
            y=summary.get_column("goals").to_list(),
            mode="markers",
            name="Team hover targets",
            marker={"size": 26, "opacity": 0.001, "color": colors},
            customdata=hover_rows,
            hovertemplate=(
                "<b>%{customdata[0]}</b><br>League: %{customdata[1]}<br>Goals: %{y}<br>"
                "xG: %{x:.2f}<br>Goals - xG: %{customdata[2]:.2f}<extra></extra>"
                if league_column
                else "<b>%{customdata[0]}</b><br>Goals: %{y}<br>xG: %{x:.2f}<br>"
                "Goals - xG: %{customdata[2]:.2f}<extra></extra>"
            ),
            showlegend=False,
        )
    )
    if missing:
        missing_x = [float(cast("float", row["xg"])) for row in missing]
        missing_y = [float(cast("float", row["goals"])) for row in missing]
        figure.add_trace(
            go.Scatter(
                x=missing_x,
                y=missing_y,
                mode="markers",
                name="Missing crest fallback",
                marker={"size": 9, "color": missing_colors},
                text=[str(row["team"]) for row in missing],
                hoverinfo="skip",
            )
        )


def team_goals_vs_xg(
    team_match_stats: pl.DataFrame,
    season: int,
    *,
    logo_paths: Mapping[str, Path] | None = None,
) -> go.Figure:
    """Plot actual team goals against provider-specific expected goals.

    Returns:
        A Plotly figure with team crests, regression, and equal axis scales.
    """
    summary = (
        team_xg_summary(team_match_stats)
        .drop_nulls(["goals", "xg"])
        .with_columns(pl.col("xg").alias("xg"), pl.col("goals").cast(pl.Float64).alias("goals"))
    )
    figure = go.Figure()
    figure.update_layout(
        title=f"Bundesliga team goals vs xG ({season}/{season + 1})",
        xaxis_title="Expected goals (provider model)",
        yaxis_title="Actual goals",
    )
    if summary.height:
        _add_team_markers(figure, summary, logo_paths if logo_paths is not None else {})
    r_squared = _add_linear_regression(figure, summary)
    _set_r_squared_title(figure, f"Bundesliga team goals vs xG ({season}/{season + 1})", r_squared)
    _set_equal_xy_scale(figure, summary, "xg", "goals")
    return figure


def player_goals_vs_xg(player_stats: pl.DataFrame, season: int, *, label_limit: int = 10) -> go.Figure:
    """Plot player goals against xG, with goal over/under-performance on hover.

    Returns:
        A Plotly figure with player labels, team colors, and regression.
    """
    return _player_scatter(
        player_stats,
        title=f"Bundesliga player goals vs xG ({season}/{season + 1})",
        xg_label="Expected goals (provider model)",
        league_detail=False,
        label_limit=label_limit,
    )


def multi_league_player_goals_vs_xg(
    player_stats: pl.DataFrame,
    season: int,
    *,
    label_limit: int = 10,
) -> go.Figure:
    """Plot Big Five player goals against xG with league included in hover details.

    Returns:
        A Plotly figure with player labels, league hover details, and regression.
    """
    return _player_scatter(
        player_stats,
        title=f"Big Five player goals vs xG ({season}/{season + 1})",
        xg_label="Expected goals (Understat model)",
        league_detail=True,
        label_limit=label_limit,
    )


def multi_league_team_goals_vs_xg(
    summary: pl.DataFrame,
    season: int,
    *,
    logo_paths: Mapping[tuple[str, str], Path] | None = None,
) -> go.Figure:
    """Plot Big Five team goals against xG with league identity in hover details.

    Returns:
        A Plotly figure with team crests, league hover details, and regression.
    """
    points = summary.drop_nulls(["goals", "xg"]).with_columns(
        pl.col("xg").cast(pl.Float64), pl.col("goals").cast(pl.Float64)
    )
    figure = go.Figure()
    figure.update_layout(
        title=f"Big Five team goals vs xG ({season}/{season + 1})",
        xaxis_title="Expected goals (Understat model)",
        yaxis_title="Actual goals",
    )
    if points.height:
        keyed_paths: Mapping[tuple[str, str], Path] = logo_paths if logo_paths is not None else {}
        _add_team_markers(figure, points, keyed_paths, league_column="league")
    r_squared = _add_linear_regression(figure, points)
    _set_r_squared_title(figure, f"Big Five team goals vs xG ({season}/{season + 1})", r_squared)
    _set_equal_xy_scale(figure, points, "xg", "goals")
    return figure


def multi_league_team_xg_for_against_per90(  # ruff: ignore[too-many-locals] - Plotly needs separate geometry and hover data.
    summary: pl.DataFrame,
    season: int,
    *,
    logo_paths: Mapping[tuple[str, str], Path] | None = None,
) -> go.Figure:
    """Plot Big Five team xG for and against per 90 with four global quadrants.

    Returns:
        A Plotly figure with quadrants, club crests, and hover details.
    """
    points = summary.drop_nulls(["league", "team", "xg_for_per90", "xg_against_per90"])
    figure = go.Figure()
    figure.update_layout(
        title=f"Big Five team xG for and against per 90 ({season}/{season + 1})",
        xaxis_title="Expected goals for per 90",
        yaxis_title="Expected goals against per 90",
    )
    _set_equal_xy_scale(figure, points, "xg_for_per90", "xg_against_per90")
    if points.is_empty():
        return figure

    categories = [
        "High attack · strong defense",
        "High attack · leaky defense",
        "Low attack · strong defense",
        "Low attack · leaky defense",
    ]
    quadrant_colors = {
        "High attack · strong defense": "#197A53",
        "High attack · leaky defense": "#C5523F",
        "Low attack · strong defense": "#5478A5",
        "Low attack · leaky defense": "#9A6C9F",
    }
    average_x = points.get_column("xg_for_per90").mean()
    average_y = points.get_column("xg_against_per90").mean()
    x_values = [float(cast("float", value)) for value in points.get_column("xg_for_per90").to_list()]
    y_values = [float(cast("float", value)) for value in points.get_column("xg_against_per90").to_list()]
    x_min = min(0.0, *x_values, *y_values)
    x_max = max(x_values + y_values) * 1.08
    y_min = x_min
    y_max = x_max
    for category, x0, x1, y0, y1 in (
        (categories[0], average_x, x_max, y_min, average_y),
        (categories[1], average_x, x_max, average_y, y_max),
        (categories[2], x_min, average_x, y_min, average_y),
        (categories[3], x_min, average_x, average_y, y_max),
    ):
        figure.add_shape(
            type="rect",
            x0=x0,
            x1=x1,
            y0=y0,
            y1=y1,
            fillcolor=quadrant_colors[category],
            opacity=0.055,
            line={"width": 0},
            layer="below",
        )
    logo_mapping: Mapping[tuple[str, str], Path] = logo_paths if logo_paths is not None else {}
    missing_rows: list[dict[str, object]] = []
    missing_colors: list[str] = []
    for row in points.iter_rows(named=True):
        league = str(row["league"])
        team = str(row["team"])
        source = _logo_source(logo_mapping.get((league, team)))
        if source is None:
            missing_rows.append(row)
            missing_colors.append(team_marker_colors(team)[0])
        else:
            figure.add_layout_image(
                source=source,
                x=float(row["xg_for_per90"]),
                y=float(row["xg_against_per90"]),
                xref="x",
                yref="y",
                xanchor="center",
                yanchor="middle",
                sizex=0.3,
                sizey=0.3,
                sizing="contain",
                layer="above",
            )

    figure.add_trace(
        go.Scatter(
            x=points.get_column("xg_for_per90").to_list(),
            y=points.get_column("xg_against_per90").to_list(),
            mode="markers",
            name="Team hover targets",
            marker={"size": 24, "opacity": 0.001},
            customdata=[
                [row["league"], row["team"], row["matches"], row["quadrant"]] for row in points.iter_rows(named=True)
            ],
            hovertemplate=(
                "<b>%{customdata[1]}</b><br>League: %{customdata[0]}<br>"
                "xG for/90: %{x:.2f}<br>xG against/90: %{y:.2f}<br>"
                "Matches: %{customdata[2]}<br>%{customdata[3]}<extra></extra>"
            ),
            showlegend=False,
        )
    )
    if missing_rows:
        figure.add_trace(
            go.Scatter(
                x=[float(cast("float", row["xg_for_per90"])) for row in missing_rows],
                y=[float(cast("float", row["xg_against_per90"])) for row in missing_rows],
                mode="markers",
                name="Missing crest fallback",
                marker={"size": 11, "color": missing_colors, "line": {"color": "#FFFFFF", "width": 1}},
                text=[str(row["team"]) for row in missing_rows],
                hoverinfo="skip",
                showlegend=False,
            )
        )

    figure.add_vline(x=average_x, line={"color": "#444444", "dash": "dash", "width": 1})
    figure.add_hline(y=average_y, line={"color": "#444444", "dash": "dash", "width": 1})
    for text, x, y, xanchor, yanchor in (
        (categories[0], 0.99, 0.02, "right", "bottom"),
        (categories[1], 0.99, 0.98, "right", "top"),
        (categories[2], 0.01, 0.02, "left", "bottom"),
        (categories[3], 0.01, 0.98, "left", "top"),
    ):
        figure.add_annotation(
            text=text,
            x=x,
            y=y,
            xref="paper",
            yref="paper",
            xanchor=xanchor,
            yanchor=yanchor,
            showarrow=False,
            font={"size": 10, "color": "#555555"},
        )
    return figure


def multi_league_xg_for_against_distribution(  # ruff: ignore[too-many-locals] - The figure uses per-league means, spreads, and fill traces.
    summary: pl.DataFrame, season: int
) -> go.Figure:
    """Show league means with team-level plus/minus one standard deviation areas.

    Returns:
        A Plotly figure with one mean and spread area per league.

    Raises:
        ValueError: If a non-empty summary is missing required columns.
    """
    required = {
        "league",
        "teams",
        "mean_xg_for_per90",
        "std_xg_for_per90",
        "mean_xg_against_per90",
        "std_xg_against_per90",
    }
    missing = required.difference(summary.columns)
    if summary.height and missing:
        msg = f"League xG summary is missing columns: {', '.join(sorted(missing))}"
        raise ValueError(msg)

    figure = go.Figure()
    figure.update_layout(
        title=f"League mean xG for and against per 90 ({season}/{season + 1}) · mean ± 1 SD",
        xaxis_title="Mean team xG for per 90",
        yaxis_title="Mean team xG against per 90",
        width=900,
        height=900,
        legend_title="League",
    )
    if summary.is_empty():
        figure.update_xaxes(range=[0.0, 1.0], constrain="domain")
        figure.update_yaxes(range=[0.0, 1.0], scaleanchor="x", scaleratio=1, constrain="domain")
        return figure
    points = summary.drop_nulls(list(required)).sort("league")
    if points.is_empty():
        figure.update_xaxes(range=[0.0, 1.0], constrain="domain")
        figure.update_yaxes(range=[0.0, 1.0], scaleanchor="x", scaleratio=1, constrain="domain")
        return figure

    lower_bounds: list[float] = [0.0]
    upper_bounds: list[float] = [0.0]
    for row in points.iter_rows(named=True):
        league = str(row["league"])
        color = LEAGUE_COLORS.get(league, "#52677F")
        mean_x = float(row["mean_xg_for_per90"])
        std_x = float(row["std_xg_for_per90"])
        mean_y = float(row["mean_xg_against_per90"])
        std_y = float(row["std_xg_against_per90"])
        x0, x1 = mean_x - std_x, mean_x + std_x
        y0, y1 = mean_y - std_y, mean_y + std_y
        lower_bounds.extend((x0, y0))
        upper_bounds.extend((x1, y1))
        figure.add_shape(
            type="rect",
            name=f"{league} ±1 SD",
            x0=x0,
            x1=x1,
            y0=y0,
            y1=y1,
            fillcolor=color,
            opacity=0.16,
            line={"color": color, "width": 2},
            layer="below",
            showlegend=False,
        )
        league_name = league.replace("-", " ").title()
        figure.add_trace(
            go.Scatter(
                x=[mean_x],
                y=[mean_y],
                mode="markers+text",
                name=league_name,
                text=[league_name],
                textposition="top center",
                marker={"color": color, "size": 13, "symbol": "diamond"},
                customdata=[[row["teams"], std_x, std_y]],
                hovertemplate=(
                    f"<b>{league_name}</b><br>Teams: %{{customdata[0]}}<br>"
                    "Mean xG for/90: %{x:.2f} ± %{customdata[1]:.2f}<br>"
                    "Mean xG against/90: %{y:.2f} ± %{customdata[2]:.2f}<extra></extra>"
                ),
            )
        )

    lower = min(lower_bounds)
    upper = max(upper_bounds)
    if upper == lower:
        upper = lower + 1.0
    padding = (upper - lower) * 0.08
    lower -= padding if lower < 0 else 0.0
    upper += padding
    figure.update_xaxes(range=[lower, upper], constrain="domain")
    figure.update_yaxes(range=[lower, upper], scaleanchor="x", scaleratio=1, constrain="domain")
    return figure


def shot_map(shots: pl.DataFrame, match_id: str | None = None) -> go.Figure:
    """Plot Understat shot locations in their provider-native coordinate system.

    Returns:
        A Plotly figure of selected shots, if available.
    """
    selected = shots
    if match_id is not None:
        selected = selected.filter(pl.col("source_match_id") == match_id)
    figure = px.scatter(
        selected,
        x="x",
        y="y",
        color="xg",
        hover_data=[column for column in ("minute", "outcome", "source_player_id") if column in selected.columns],
        labels={"x": "Understat x coordinate", "y": "Understat y coordinate", "xg": "Understat xG"},
        title="Shot locations (Understat native coordinates)",
    )
    figure.update_yaxes(scaleanchor="x", scaleratio=1)
    return figure
