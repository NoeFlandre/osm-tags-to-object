from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class TagFilter:
    """A set of OSM tag key/value pairs used to select objects.

    Values may be a single string or a list of strings (OR semantics).
    Example: {"amenity": "bench"} or {"amenity": ["bench", "fountain"]}.
    """

    tags: dict[str, str | list[str]]
