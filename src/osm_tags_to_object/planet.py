from __future__ import annotations

from collections.abc import Iterator
from typing import Any

from .checkpoint import Checkpoint
from .client import OverpassClient
from .models import OSMObject
from .pipeline import fetch_matching_objects
from .tags import TagFilter
from .tiles import TileGrid


def fetch_planet(
    tags: dict[str, str | list[str]],
    bbox: tuple[float, float, float, float],
    checkpoint: Checkpoint,
    tile_rows: int = 4,
    tile_cols: int = 4,
    client: OverpassClient | None = None,
) -> Iterator[OSMObject]:
    """Fetch matching OSM objects across ``bbox`` tile-by-tile.

    Skips any tile whose key is already present in ``checkpoint``; for the
    remaining tiles, yields the matching objects and marks the tile done
    once the response has been fully consumed. An empty response still
    marks the tile done, so empty areas are not re-queried on resume.

    If a tile fetch raises, earlier tiles stay marked done and the failing
    tile is left unmarked so a subsequent run retries it.
    """
    owns_client = client is None
    client = client or OverpassClient()
    try:
        grid = TileGrid(bbox, rows=tile_rows, cols=tile_cols)
        filter_obj = TagFilter(tags)
        for tile in grid:
            if checkpoint.is_done(tile.key):
                continue
            objects = fetch_matching_objects(
                filter_obj, bbox=tile.bbox, client=client
            )
            yield from objects
            checkpoint.mark_done(tile.key)
    finally:
        if owns_client:
            client.close()
