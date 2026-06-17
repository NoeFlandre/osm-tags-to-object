from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class OSMObject:
    """An OSM way or relation (nodes are excluded by design)."""

    type: str  # "way" | "relation"
    id: int
    tags: dict[str, str] = field(default_factory=dict)
    nodes: tuple[int, ...] = ()
    members: tuple[dict[str, Any], ...] = ()
