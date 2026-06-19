from __future__ import annotations

from .client import OverpassClient
from .models import OSMObject
from .parser import parse_osm_elements
from .query import build_overpass_query
from .tags import TagFilter


def fetch_matching_objects(
    filter: TagFilter,
    bbox: tuple[float, float, float, float] | None = None,
    client: OverpassClient | None = None,
) -> list[OSMObject]:
    """Build an Overpass query, fetch the matching objects, and parse them.

    Nodes are filtered out. Only ways and relations are returned.
    """
    owns_client = client is None
    client = client or OverpassClient()
    try:
        query = build_overpass_query(filter, bbox=bbox)
        data = client.fetch(query)
    finally:
        if owns_client:
            client.close()
    return parse_osm_elements(data)
