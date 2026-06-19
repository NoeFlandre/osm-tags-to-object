"""Build a map-friendly GeoJSON from the parquet dataset.

Reads ``./data/france-forest.parquet`` (large) and writes
``./data/france-forest.map.geojson`` (small enough for folium).

Steps:
1. Drop relations entirely - they're multipolygons whose geometry we'd
   have to reassemble, and they tend to be large aggregated forests
   already represented by their constituent ways.
2. Keep ways whose bbox area (deg^2) exceeds ``--min-bbox-area`` so the
   map only shows forests that are visually meaningful at country zoom.
3. Simplify each remaining polygon with Ramer-Douglas-Peucker so the
   GeoJSON doesn't dwarf the actual content.
"""

from __future__ import annotations

import argparse
import json
import math
from pathlib import Path

import pyarrow.parquet as pq

# Approximate metres per degree at France's latitude (~46 deg).
# Used only for size heuristics, not for accurate cartography.
METRES_PER_DEG_LAT = 111_320.0
METRES_PER_DEG_LON_AT_46 = 111_320.0 * math.cos(math.radians(46.0))  # ~77,400


def bbox_area_deg2(coords: list[tuple[float, float]]) -> float:
    """Return the bbox area of a (lat, lon) polyline in deg^2."""
    if not coords:
        return 0.0
    lats = [p[0] for p in coords]
    lons = [p[1] for p in coords]
    return (max(lats) - min(lats)) * (max(lons) - min(lons))


def bbox_area_km2(coords: list[tuple[float, float]]) -> float:
    """Return the bbox area of a (lat, lon) polyline in km^2."""
    if not coords:
        return 0.0
    lats = [p[0] for p in coords]
    lons = [p[1] for p in coords]
    d_lat = (max(lats) - min(lats)) * METRES_PER_DEG_LAT / 1000.0
    d_lon = (max(lons) - min(lons)) * METRES_PER_DEG_LON_AT_46 / 1000.0
    return d_lat * d_lon


def rdp(points: list[tuple[float, float]], epsilon: float) -> list[tuple[float, float]]:
    """Ramer-Douglas-Peucker simplification on a (lat, lon) polyline."""
    if len(points) < 3:
        return list(points)

    def perp_dist(p, a, b):
        ax, ay = a
        bx, by = b
        px, py = p
        dx, dy = bx - ax, by - ay
        if dx == 0 and dy == 0:
            return math.hypot(px - ax, py - ay)
        t = ((px - ax) * dx + (py - ay) * dy) / (dx * dx + dy * dy)
        t = max(0.0, min(1.0, t))
        cx, cy = ax + t * dx, ay + t * dy
        return math.hypot(px - cx, py - cy)

    # Find point with max distance from line a->b
    a, b = points[0], points[-1]
    max_d = 0.0
    max_i = 0
    for i in range(1, len(points) - 1):
        d = perp_dist(points[i], a, b)
        if d > max_d:
            max_d = d
            max_i = i
    if max_d > epsilon:
        left = rdp(points[: max_i + 1], epsilon)
        right = rdp(points[max_i:], epsilon)
        return left[:-1] + right
    return [a, b]


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", default="./data/france-forest.parquet")
    parser.add_argument("--output", default="./data/france-forest.map.geojson")
    parser.add_argument(
        "--min-bbox-km2",
        type=float,
        default=0.5,
        help="Drop ways with bbox area below this threshold (km^2).",
    )
    parser.add_argument(
        "--rdp-epsilon-deg",
        type=float,
        default=0.0005,
        help="RDP simplification tolerance in degrees (~50 m at France's latitude).",
    )
    args = parser.parse_args()

    in_path = Path(args.input)
    out_path = Path(args.output)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    table = pq.read_table(in_path)
    rows = table.to_pylist()
    total = len(rows)
    print(f"Read {total:,} rows from {in_path}")

    written = 0
    skipped_rel = 0
    skipped_small = 0
    skipped_empty = 0
    kept_polygons = 0
    raw_vertices = 0
    simplified_vertices = 0

    with out_path.open("w", encoding="utf-8") as out:
        out.write('{"type": "FeatureCollection", "features": [\n')
        first = True
        for row in rows:
            if row["type"] != "way":
                skipped_rel += 1
                continue
            geom = row["geometry"] or []
            if not geom:
                skipped_empty += 1
                continue
            coords = [(p["lat"], p["lon"]) for p in geom]
            raw_vertices += len(coords)
            if bbox_area_km2(coords) < args.min_bbox_km2:
                skipped_small += 1
                continue
            simplified = rdp(coords, args.rdp_epsilon_deg)
            simplified_vertices += len(simplified)
            if len(simplified) < 3:
                skipped_small += 1
                continue
            ring = [[lon, lat] for lat, lon in simplified]
            ring.append(ring[0])  # close the ring
            feature = {
                "type": "Feature",
                "id": row["id"],
                "osm_type": "way",
                "properties": dict(row["tags"]),
                "geometry": {"type": "Polygon", "coordinates": [ring]},
            }
            if not first:
                out.write(",\n")
            first = False
            out.write("  ")
            out.write(json.dumps(feature, ensure_ascii=False))
            written += 1
            kept_polygons += 1
        out.write("\n]}\n")

    print(f"Relations skipped:    {skipped_rel:,}")
    print(f"Empty geometry:       {skipped_empty:,}")
    print(f"Below size threshold: {skipped_small:,}")
    print(f"Features written:     {written:,}")
    print(
        f"Vertex reduction:     {raw_vertices:,} -> {simplified_vertices:,} "
        f"({100 * simplified_vertices / max(raw_vertices, 1):.1f}%)"
    )
    print(f"Output size: {out_path.stat().st_size:,} bytes")


if __name__ == "__main__":
    main()
