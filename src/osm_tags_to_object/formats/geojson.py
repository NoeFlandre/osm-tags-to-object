from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from ..models import OSMObject


class GeoJSONWriter:
    """Write OSM objects to a GeoJSON FeatureCollection as a stream.

    Ways with empty geometry are skipped (a Feature requires a geometry).
    Relation polygons are emitted as MultiPolygon features built from
    members with role ``outer``; other members are ignored for the map view.
    """

    def __init__(self, path: Path) -> None:
        self._path = path
        self._fp: Any = None
        self._count = 0

    def __enter__(self) -> "GeoJSONWriter":
        self._fp = open(self._path, "w", encoding="utf-8")
        self._fp.write('{"type": "FeatureCollection", "features": [\n')
        return self

    def __exit__(self, *exc: object) -> None:
        if self._fp is None:
            return
        if self._count > 0:
            # Drop the trailing comma from the last feature.
            self._fp.seek(self._fp.tell() - 2)
            self._fp.truncate()
            self._fp.write("\n")
        self._fp.write("]}\n")
        self._fp.close()
        self._fp = None

    def write(self, obj: OSMObject) -> None:
        if self._fp is None:
            raise RuntimeError("GeoJSONWriter must be used as a context manager")
        feature = _to_feature(obj)
        if feature is None:
            return
        self._fp.write("  ")
        self._fp.write(json.dumps(feature, ensure_ascii=False))
        self._fp.write(",\n")
        self._count += 1


def _to_feature(obj: OSMObject) -> dict[str, Any] | None:
    base = {
        "type": "Feature",
        "id": obj.id,
        "osm_type": obj.type,
        "properties": dict(obj.tags),
    }
    if obj.type == "way":
        if not obj.geometry:
            return None
        ring = [[lon, lat] for lat, lon in obj.geometry]
        ring.append(ring[0])  # close the ring
        return {**base, "geometry": {"type": "Polygon", "coordinates": [ring]}}
    if obj.type == "relation":
        rings = [
            [[lon, lat] for lat, lon in _member_geometry(m)]
            for m in obj.members
            if m.get("type") == "way" and m.get("role") == "outer"
        ]
        if not rings:
            return None
        # GeoJSON linear rings must repeat their first coordinate.
        rings = [ring + [ring[0]] for ring in rings]
        geometry_type = "MultiPolygon" if len(rings) > 1 else "Polygon"
        coordinates = (
            [[ring] for ring in rings] if geometry_type == "MultiPolygon" else [rings[0]]
        )
        return {**base, "geometry": {"type": geometry_type, "coordinates": coordinates}}
    return None


def _member_geometry(member: dict[str, Any]) -> tuple[tuple[float, float], ...]:
    raw = member.get("geometry", ())
    return tuple((float(p["lat"]), float(p["lon"])) for p in raw)
