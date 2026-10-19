# Soccer analytics workspace

A local research workspace for professional soccer data. The `uv` workspace separates provider adapters (`soccer-sources`), reusable Polars analysis (`soccer-analysis`), and Plotly figures (`soccer-visualization`). Marimo notebooks in `scripts/` combine those packages. The xG notebook compares the Bundesliga and the available Big Five league caches.

## Quickstart

Install Python 3.14 and [uv](https://docs.astral.sh/uv/), then run:

```sh
uv sync
uv run soccer-data openligadb --league bundesliga --season 2026
uv run marimo edit scripts/big5_xg.py
```

The OpenLigaDB command downloads 2026/27 fixtures and results and stores normalized Parquet under `.cache/soccer/`. The notebook displays cached source data and omits xG charts until real Understat tables have been ingested; it does not substitute example rows. Understat ingestion is separate and opt-in because it reads a third-party website; read [data source notes](docs/data-sources.md) before enabling it. In the notebook, use **Refresh cached data from providers** to refresh OpenLigaDB fixtures/results, Understat team and player tables for all five leagues, and team crests. The notebook performs no provider requests until that button is clicked.

To retrieve 2026/27 Understat team and player xG after reviewing the access notes, install its optional dependency group with `uv sync --group understat`, then run `uv run soccer-data understat --league bundesliga --season 2026 --allow-scraping`. Repeat with `premier-league`, `la-liga`, `serie-a`, and `ligue-1` for the Big Five chart. Add `--refresh` to bypass local caches.

The Big Five notebook includes a team xG-for versus xG-against per-90 plot. Its four quadrants classify teams relative to the combined Big Five averages; the chart uses the locally cached Understat team-match rows.
Use the notebook's league selector to filter all Big Five plots and the top-scorer table; it defaults to all five leagues. The xG plots use square 900×900 canvases with matching axis scales.

Team crests are fetched separately with `uv run soccer-data logos --league bundesliga --season 2026`; repeat for each league used in the notebook. They are cached locally and used only when present. The catalog's reuse terms are unclear, so read the crest notes in [data source documentation](docs/data-sources.md) before sharing plots that include crests.

Install the repository hooks once with `uv run prek install`.

## Development

```sh
uv run pytest
uv run prek run --all-files
uv run ruff format .
```

See [AGENTS.md](AGENTS.md) for package boundaries and offline testing rules. No event-data or player-tracking pipeline is included.
