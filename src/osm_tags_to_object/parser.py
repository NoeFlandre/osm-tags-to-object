from __future__ import annotations

from typing import Any

from .models import OSMObject

_ALLOWED_TYPES = frozenset({"way", "relation"})


def _extract_geometry(element: dict[str, Any]) -> tuple[tuple[float, float], ...]:
    """Pull the (lat, lon) tuples from an Overpass element with ``out geom;``."""
    raw = element.get("geometry", ())
    return tuple((float(p["lat"]), float(p["lon"])) for p in raw)


def parse_osm_elements(data: dict[str, Any]) -> list[OSMObject]:
    """Parse an Overpass JSON response into OSMObject instances.

    Nodes are always dropped; only ways and relations are returned.
    Each way's ``geometry`` is its node coordinates in order.
    Each relation keeps its raw ``members`` (which may carry their own geometry).
    """
    elements = data.get("elements", [])
    objects: list[OSMObject] = []
    for element in elements:
        element_type = element.get("type")
        if element_type not in _ALLOWED_TYPES:
            continue
        objects.append(
            OSMObject(
                type=element_type,
                id=element["id"],
                tags=element.get("tags", {}),
                geometry=_extract_geometry(element),
                members=tuple(element.get("members", ())),
            )
        )
    return objects
