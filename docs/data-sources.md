# Data source notes

## OpenLigaDB

The OpenLigaDB JSON API provides match schedules, team identifiers, kickoff times, and results without an API key. The adapter reads one season from `getmatchdata/{league}/{season}`, normalizes matches into Polars, and stores the raw JSON plus Parquet table under `.cache/soccer/openligadb/`. The API endpoint is `https://api.openligadb.de/`; attribute OpenLigaDB when redistributing derived data. The source identifies its data as Open Database License (ODbL), so adapted databases may carry attribution and share-alike requirements. Review the current source terms before redistribution.

Live smoke test on 2026-10-18: `getmatchdata/bl1/2025` returned 306 match records. The same command then reads the normalized Parquet cache without a network request.

The Marimo notebook is set to the 2026/27 season (season start year `2026`). A live refresh on 2026-10-18 cached 306 OpenLigaDB match records, including the season fixtures and results available at retrieval time. The notebook reads that cache; it never fills gaps with fabricated rows.

## Understat through soccerdata

The `soccerdata` adapter exposes the documented Understat methods for schedules, team-match statistics, player season statistics, and shot events. Install it with `uv sync --group understat`; keeping it optional avoids installing its browser-testing dependencies for the default OpenLigaDB workflow. The adapter flattens pandas indexes/columns and returns Polars tables, preserving source identifiers and unrecognized provider metrics where available. Understat xG is a provider-specific model and must not be mixed with another provider's xG as if values were identical. Shot coordinates are retained in Understat's native coordinate system and should not be combined with other providers' locations without a validated transform.

Understat is a third-party website, not a documented bulk-data API. The current `soccerdata` reference describes scraping and local caching, and documents proxy rotation as a feature; this project does not configure proxies or evade access controls. I could not establish a clear permission statement or verify robots guidance during setup. For that reason, every Understat loader is disabled unless `allow_scraping=True`, and the CLI requires `--allow-scraping`. Review the current Understat terms and robots policy before repeated ingestion. If access is not permitted or the site blocks a request, use already cached files and do not retry around the restriction.

An opt-in retrieval on 2026-10-18 cached 392 Bundesliga player-season rows. The initial normalizer appeared to return no team-match rows because `soccerdata` supplies one wide record per match (`home_*` and `away_*`) while the adapter expected one team per row. This was a normalization bug, not missing source data. The adapter now expands each finished match into two team rows and maps the opponent's xG to `xga`.

Big Five cache check on 2026-10-19: Understat has 392 Bundesliga, 446 Premier League, 474 La Liga, 472 Serie A, and 418 Ligue 1 player-season rows (2,202 total). Normalized team-match caches contain 104 Bundesliga, 138 Premier League, 174 La Liga, 136 Serie A, and 126 Ligue 1 team rows (678 total, two rows per match). The xG-for/against chart averages each team's valid match xG and xGA, equivalent to per-90 rates over regulation match time, then classifies all 96 teams against the combined Big Five means. Values are season-to-date, not final-season totals. No shot-event table is cached, so shot maps remain unavailable unless that separate ingestion is enabled and succeeds. Understat is an unofficial third-party scraper; review current terms before repeated retrieval or redistribution.

## Provenance and cache

Normalized tables contain provider, provider API/library version, league, season, source URL, and retrieval timestamp columns. Missing provider IDs remain null; names are not silently substituted for IDs. Cache files are local, ignored by Git, and can be rebuilt with the CLI `--refresh` option. Tests use fixed local records and never call a provider.

## Team crests

Team crests are available from the public [`luukhopman/football-logos` catalog](https://github.com/luukhopman/football-logos), which lists team PNGs for the top 25 European leagues from 2021/22 through 2026/27. The source organizes the current season under `logos/` and earlier seasons under `history/`. `uv run soccer-data logos --league bundesliga --season 2026` downloads the selected league's crests into `.cache/soccer/logos/`; repeat for `premier-league`, `la-liga`, `serie-a`, and `ligue-1` to populate the Big Five. Notebook rendering reads only those local files and does not make network requests.

Provider team names are matched against catalog filenames using explicit aliases and normalized spelling. Missing or unmatched names are left without a crest and shown as markers in the plot; names are never guessed. The catalog does not state clear reuse terms, and club crests are trademarks. Treat these assets as local research material. Clear rights independently before redistributing figures that include crests.

Live catalog check on 2026-10-19 cached 96 PNGs: 18 Bundesliga, 20 Premier League, 20 La Liga, 20 Serie A, and 18 Ligue 1. All 96 Understat team names in the corresponding local cache matched a crest after explicit alias mapping. The catalog can change; new or renamed teams may require additional aliases.
