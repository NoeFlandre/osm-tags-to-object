"""Output format writers (GeoJSON, Parquet)."""

from __future__ import annotations

from pathlib import Path
from typing import Literal

from ..models import OSMObject
from .base import FormatWriter
from .geojson import GeoJSONWriter

__all__ = ["FormatWriter", "GeoJSONWriter", "open_writer"]


def open_writer(path: Path, format: Literal["geojson", "parquet"]) -> FormatWriter:
    """Return a context-managed writer for the given output path and format.

    Format is inferred from the file suffix when ``format`` is "auto".
    """
    if format == "geojson":
        return GeoJSONWriter(path)
    if format == "parquet":
        from .parquet import ParquetWriter  # local import: optional dep

        return ParquetWriter(path)
    raise ValueError(f"Unknown format: {format!r}")
