"""Download OpenStreetMap ways + relations that match a set of tags.

Quickstart (programmatic)::

    from osm_tags_to_object import fetch_matching_objects, TagFilter
    objects = fetch_matching_objects(
        TagFilter({"amenity": ["bench", "fountain"]}),
        bbox=(43.7, 7.4, 43.8, 7.5),
    )

Quickstart (CLI)::

    osm-tags-to-object fetch \\
        --tags amenity=bench,fountain \\
        --bbox 43.7,7.4,43.8,7.5 \\
        -o ./data/monaco.geojson
    osm-tags-to-object map -i ./data/monaco.geojson -o ./data/monaco.html
"""

from .client import OverpassClient
from .models import OSMObject
from .pipeline import fetch_matching_objects
from .retry import RetryConfig
from .storage import write_objects
from .tags import TagFilter

__all__ = [
    "OSMObject",
    "OverpassClient",
    "RetryConfig",
    "TagFilter",
    "fetch_matching_objects",
    "write_objects",
]

__version__ = "0.1.0"
