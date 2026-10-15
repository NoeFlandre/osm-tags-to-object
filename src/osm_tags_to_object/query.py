from __future__ import annotations

from .tags import TagFilter

_ELEMENT_TYPES = ("way", "relation")


def _iter_tag_selectors(filter: TagFilter) -> list[tuple[str, str]]:
    selectors: list[tuple[str, str]] = []
    for key, value in filter.tags.items():
        values = value if isinstance(value, list) else [value]
        selectors.extend((key, v) for v in values)
    return selectors


def build_overpass_query(
    filter: TagFilter,
    bbox: tuple[float, float, float, float] | None = None,
    timeout: int = 25,
) -> str:
    """Build an Overpass QL query selecting ways and relations matching the tags.

    If bbox is provided as (south, west, north, east), the selection is
    constrained to that area. Otherwise the query is planet-wide.

    Nodes are never selected.
    """
    bbox_clause = (
        f"({bbox[0]},{bbox[1]},{bbox[2]},{bbox[3]})" if bbox is not None else ""
    )

    selectors = _iter_tag_selectors(filter)
    lines: list[str] = []
    for element_type in _ELEMENT_TYPES:
        for key, value in selectors:
            lines.append(f'  {element_type}["{key}"="{value}"]{bbox_clause};')

    body = "\n".join(lines)
    return (
        f"[out:json][timeout:{timeout}];\n"
        f"(\n"
        f"{body}\n"
        f");\n"
        f"out geom;"
    )
