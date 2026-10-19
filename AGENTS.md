# Repository guidance

- Use `uv` for the Python 3.14 workspace and dependency changes; do not edit `uv.lock` by hand.
- Keep provider access and provider IDs in `soccer-sources`, provider-independent Polars analysis in `soccer-analysis`, and figures in `soccer-visualization`.
- Preserve the one-way dependency order: visualization → analysis → sources. Analysis must not import adapters.
- Keep network access out of imports, notebooks' visualization cells, and routine tests. Test adapters with fixed local fixtures.
- Store downloads and Parquet tables under `.cache/`; do not commit full-season data or credentials.
- Keep tests inside their corresponding package under `tests/<package_name>/`; use fixed local fixtures for provider tests.
- Format and lint with Ruff, check types with ty, and run `uv run prek run --all-files` plus `uv run pytest` before finishing.
