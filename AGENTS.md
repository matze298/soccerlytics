# Repository guidance

- Use `uv` for the Python 3.14 workspace and dependency changes; do not edit `uv.lock` by hand.
- Keep provider access and provider IDs in `soccer-sources`, provider-independent Polars analysis in `soccer-analysis`, and figures in `soccer-visualization`.
- Preserve the one-way dependency order: visualization → analysis → sources. Analysis must not import adapters.
- Keep network access out of imports, notebooks' visualization cells, and routine tests. Test adapters with fixed local fixtures.
- Store downloads and Parquet tables under `.cache/`; do not commit full-season data or credentials.
- Keep tests inside their corresponding package under `tests/<package_name>/`; use fixed local fixtures for provider tests.
- Format and lint with Ruff, check types with ty, and run `uv run prek run --all-files` plus `uv run pytest` before finishing.
- Keep changes within the requested scope; do not rename or reformat unrelated files.
- Fix Ruff findings where practical. Use rule names for exceptions, prefer a narrow line-level ignore with a short reason, and reserve file-wide exceptions for real file conventions such as Marimo cells and pytest assertions.
- Test behavior implemented by this repository, not third-party internals or checks owned by external tools. Use fixed local inputs and explicit test doubles at provider boundaries.
- Keep unit tests out of prek hooks and run them separately with `uv run pytest`.
