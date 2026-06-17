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

Quickstart (resumable planet-wide fetch)::

    osm-tags-to-object planet \\
        --tags amenity=bench \\
        --bbox -90,-180,90,180 \\
        --tile-rows 18 --tile-cols 36 \\
        --checkpoint ./data/checkpoint.json \\
        -o ./data/planet.geojson
    # Re-running the same command resumes from the checkpoint file.
"""

from .checkpoint import Checkpoint, FileCheckpointStore
from .client import OverpassClient
from .models import OSMObject
from .pipeline import fetch_matching_objects
from .planet import fetch_planet
from .retry import RetryConfig
from .storage import write_objects
from .tags import TagFilter
from .tiles import Tile, TileGrid

__all__ = [
    "Checkpoint",
    "FileCheckpointStore",
    "OSMObject",
    "OverpassClient",
    "RetryConfig",
    "TagFilter",
    "Tile",
    "TileGrid",
    "fetch_matching_objects",
    "fetch_planet",
    "write_objects",
]

__version__ = "0.1.0"
