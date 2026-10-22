"""Local raw-response and normalized Parquet cache helpers."""

import json
from pathlib import Path
from typing import cast

import polars as pl

DEFAULT_CACHE_DIR = Path(".cache/soccer")

type JsonValue = bool | int | float | str | list[JsonValue] | dict[str, JsonValue] | None


def cache_file(  # ruff: ignore[too-many-arguments] - Cache identity requires provider, entity, league, and season inputs.
    provider: str,
    entity: str,
    league: str,
    season: int,
    *,
    suffix: str,
    cache_dir: Path = DEFAULT_CACHE_DIR,
) -> Path:
    """Build a stable cache path for one provider table or raw response.

    Returns:
        The path for the selected cache entry.
    """
    return cache_dir / provider / league / str(season) / f"{entity}.{suffix}"


def read_parquet(path: Path) -> pl.DataFrame | None:
    """Read a cached table when present.

    Returns:
        The cached table, or ``None`` when the path does not exist.
    """
    return pl.read_parquet(path) if path.is_file() else None


def write_parquet(frame: pl.DataFrame, path: Path) -> None:
    """Write a table atomically to local Parquet storage."""
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(f"{path.suffix}.tmp")
    frame.write_parquet(temporary)
    temporary.replace(path)


def read_json(path: Path) -> JsonValue | None:
    """Read a cached JSON response when present.

    Returns:
        The decoded JSON value, or ``None`` when the path does not exist.
    """
    if not path.is_file():
        return None
    return cast("JsonValue", json.loads(path.read_text(encoding="utf-8")))


def write_json(value: JsonValue, path: Path) -> None:
    """Write a raw JSON response atomically."""
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(f"{path.suffix}.tmp")
    temporary.write_text(json.dumps(value, ensure_ascii=False), encoding="utf-8")
    temporary.replace(path)
