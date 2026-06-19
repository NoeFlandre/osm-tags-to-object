from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class OSMObject:
    """An OSM way or relation (nodes are excluded by design).

    For ways, ``geometry`` holds the (lat, lon) pairs of the way's nodes in order.
    For relations, ``members`` holds the raw member dicts as returned by Overpass;
    each member may include its own ``geometry`` list.
    """

    type: str  # "way" | "relation"
    id: int
    tags: dict[str, str] = field(default_factory=dict)
    geometry: tuple[tuple[float, float], ...] = ()
    members: tuple[dict[str, Any], ...] = ()
