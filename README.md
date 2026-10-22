# Soccer analytics workspace

A local research workspace for professional soccer data. The `uv` workspace separates provider adapters (`soccer-sources`), reusable Polars analysis (`soccer-analysis`), and Plotly figures (`soccer-visualization`). Marimo notebooks in `scripts/` combine those packages. The xG notebook compares the Bundesliga and the available Big Five league caches.

## Quickstart

Install Python 3.14 and [uv](https://docs.astral.sh/uv/), then run:

```sh
uv sync
uv run soccer-data openligadb --league bundesliga --season 2026
uv run marimo edit scripts/big5_xg.py
```

The OpenLigaDB command downloads fixtures and results and stores normalized Parquet under `.cache/soccer/`. The notebook reads cached source data and omits xG charts until real Understat tables are available; it does not substitute example rows. Selecting a season loads cached data and fetches missing OpenLigaDB and Understat tables plus every crest in the selected season catalog. Season values use the start year: `2025` means 2025/26. **Refresh cached data from providers** bypasses local caches.

To retrieve 2026/27 Understat team and player xG, run `uv run soccer-data understat --league bundesliga --season 2026`. Repeat with `premier-league`, `la-liga`, `serie-a`, and `ligue-1` for the Big Five chart. Add `--refresh` to bypass local caches.

The notebook starts with the Top Five league analysis and ends with a separate Bundesliga section. One global season selector controls both sections and offers Understat seasons from 2014/15 through the current season, regardless of which seasons are cached locally. A season with no local data shows empty charts until refreshed. Each Top Five plot and its scorer table has an independent league selector, defaulting to all five leagues. The xG plots use square 900×900 canvases with matching axis scales.

The Top Five team xG-for versus xG-against per-90 plot classifies teams relative to the combined averages. An additional league summary marks each selected league's mean and shades the mean ±1 population standard deviation across teams. The Bundesliga section repeats the player and team goals-versus-xG plots, the team per-90 quadrant plot, the league mean-and-spread plot, and the scorer table.

Team crests are fetched separately with `uv run soccer-data logos --league bundesliga --season 2026`; repeat for each league used in the notebook. They are cached locally and used only when present. The catalog's reuse terms are unclear, so read the crest notes in [data source documentation](docs/data-sources.md) before sharing plots that include crests.

Install the repository hooks once with `uv run prek install`.

## Development

```sh
uv run pytest
uv run prek run --all-files
uv run ruff format .
```

See [AGENTS.md](AGENTS.md) for package boundaries and offline testing rules. No event-data or player-tracking pipeline is included.
