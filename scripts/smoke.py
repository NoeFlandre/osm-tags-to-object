"""End-to-end live smoke check.

Run with: PYTHONPATH=src uv run python scripts/smoke.py
Fetches a small bbox from the real Overpass API, writes GeoJSON, then
renders the interactive map. Verifies all major modules cooperate.
"""

import json
from pathlib import Path

from osm_tags_to_object.client import OverpassClient
from osm_tags_to_object.map import render_map
from osm_tags_to_object.pipeline import fetch_matching_objects
from osm_tags_to_object.storage import write_objects
from osm_tags_to_object.tags import TagFilter

# Monaco bbox - small enough to finish in seconds.
MONACO_BBOX = (43.7280, 7.4090, 43.7530, 7.4380)
TAGS = {"amenity": ["bench", "fountain"]}


def main() -> None:
    out_dir = Path("./data")
    geojson_path = out_dir / "smoke_monaco.geojson"
    html_path = out_dir / "smoke_monaco.html"

    print(f"Fetching {TAGS} in {MONACO_BBOX} ...")
    with OverpassClient() as client:
        objects = fetch_matching_objects(
            TagFilter(TAGS), bbox=MONACO_BBOX, client=client
        )

    print(f"Got {len(objects)} objects. Writing {geojson_path} ...")
    write_objects(objects, geojson_path, format="geojson")

    summary = {"total": len(objects), "by_type": {}}
    for obj in objects:
        summary["by_type"][obj.type] = summary["by_type"].get(obj.type, 0) + 1
    print(json.dumps(summary, indent=2))

    print(f"Rendering map to {html_path} ...")
    render_map(geojson_path, html_path)
    print(f"Map size: {html_path.stat().st_size:,} bytes")


if __name__ == "__main__":
    main()
