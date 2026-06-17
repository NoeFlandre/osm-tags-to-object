"""Tile a bounding box into a regular grid of smaller bboxes.

Used together with :mod:`osm_tags_to_object.checkpoint` to break large
planet-wide fetches into bounded, resumable units.
"""

from __future__ import annotations

from collections.abc import Iterator
from dataclasses import dataclass


@dataclass(frozen=True)
class Tile:
    """A single sub-bbox within a :class:`TileGrid`."""

    key: str
    bbox: tuple[float, float, float, float]  # (south, west, north, east)
    row: int
    col: int


class TileGrid:
    """Split a bbox into a ``rows x cols`` grid of :class:`Tile`.

    Tiles are yielded row-major (top to bottom, left to right) so they
    are deterministic and easy to checkpoint.
    """

    def __init__(
        self,
        bbox: tuple[float, float, float, float],
        rows: int,
        cols: int,
    ) -> None:
        if rows < 1 or cols < 1:
            raise ValueError(f"rows and cols must be >= 1, got rows={rows}, cols={cols}")
        south, west, north, east = bbox
        if south >= north or west >= east:
            raise ValueError(f"invalid bbox {bbox}: south<north and west<east required")
        self._bbox = bbox
        self._rows = rows
        self._cols = cols

    def __iter__(self) -> Iterator[Tile]:
        south, west, north, east = self._bbox
        height = (north - south) / self._rows
        width = (east - west) / self._cols
        for r in range(self._rows):
            for c in range(self._cols):
                t_south = south + r * height
                t_north = south + (r + 1) * height
                t_west = west + c * width
                t_east = west + (c + 1) * width
                yield Tile(
                    key=f"tile_{t_south:.6f}_{t_west:.6f}_{t_north:.6f}_{t_east:.6f}",
                    bbox=(t_south, t_west, t_north, t_east),
                    row=r,
                    col=c,
                )

    def __len__(self) -> int:
        return self._rows * self._cols

    @property
    def total(self) -> int:
        return len(self)
