from __future__ import annotations

from typing import Any

from .models import OSMObject

# OSM element types this package cares about. Nodes are filtered out.
_ALLOWED_TYPES = frozenset({"way", "relation"})


def parse_osm_elements(data: dict[str, Any]) -> list[OSMObject]:
    """Parse an Overpass JSON response into OSMObject instances.

    Nodes are always dropped; only ways and relations are returned.
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
                nodes=tuple(element.get("nodes", ())),
                members=tuple(element.get("members", ())),
            )
        )
    return objects
