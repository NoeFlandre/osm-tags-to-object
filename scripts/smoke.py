"""Tiny end-to-end smoke check against the real Overpass API.

Run with: uv run python scripts/smoke.py
Not a test; lives outside tests/ on purpose.
"""

from osm_tags_to_object.pipeline import fetch_matching_objects
from osm_tags_to_object.tags import TagFilter


def main() -> None:
    # Monaco bounding box (~2 km x 1 km), so the call finishes in seconds.
    monaco_bbox = (43.7280, 7.4090, 43.7530, 7.4380)

    objects = fetch_matching_objects(
        TagFilter({"amenity": ["bench", "fountain"]}),
        bbox=monaco_bbox,
    )

    print(f"Fetched {len(objects)} matching objects (ways + relations only):")
    by_type: dict[str, int] = {}
    for obj in objects[:10]:
        key = f"{obj.type}:{obj.id}"
        tags_preview = ", ".join(f"{k}={v}" for k, v in list(obj.tags.items())[:3])
        print(f"  - {key}  tags=[{tags_preview}]")
        by_type[obj.type] = by_type.get(obj.type, 0) + 1

    print(f"\nBreakdown: {by_type}")


if __name__ == "__main__":
    main()
