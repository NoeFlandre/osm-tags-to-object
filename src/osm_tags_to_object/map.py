"""Render an interactive Leaflet map of OSM polygons with hover tooltips.

Uses :mod:`folium` to generate a self-contained HTML file. Each polygon's
tags appear as a tooltip on hover and a popup on click.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Iterator

import folium


def compute_bounds(
    features: list[dict[str, Any]],
) -> tuple[tuple[float, float], tuple[float, float]]:
    """Return ``(southwest, northeast)`` as ``(lat, lon)`` pairs.

    Handles both Polygon and MultiPolygon geometries and silently skips
    features with no geometry.
    """
    lats: list[float] = []
    lons: list[float] = []
    for feature in features:
        for lon, lat in _iter_points(feature.get("geometry") or {}):
            lats.append(lat)
            lons.append(lon)
    if not lats:
        raise ValueError("no coordinates found in any feature")
    return ((min(lats), min(lons)), (max(lats), max(lons)))


def _iter_points(geom: dict[str, Any]) -> Iterator[tuple[float, float]]:
    """Yield ``(lon, lat)`` tuples for all points in a GeoJSON geometry."""
    coords = geom.get("coordinates") or []
    geom_type = geom.get("type")
    if geom_type == "Polygon":
        rings = coords
    elif geom_type == "MultiPolygon":
        rings = [ring for polygon in coords for ring in polygon]
    else:
        return
    for ring in rings:
        for point in ring:
            yield float(point[0]), float(point[1])


def render_map(input_path: Path, output_path: Path) -> None:
    """Render an HTML map with one polygon feature per OSM object.

    Tooltips show ``key=value`` pairs separated by ``|`` so that hovering
    the cursor over a polygon reveals its tags. Popups show the same data
    formatted for click-to-open.
    """
    data = json.loads(input_path.read_text())
    features = data.get("features", [])
    if not features:
        raise ValueError("input GeoJSON has no features")

    sw, ne = compute_bounds(features)
    center = ((sw[0] + ne[0]) / 2.0, (sw[1] + ne[1]) / 2.0)

    folium_map = folium.Map(location=center, zoom_start=13)

    for feature in features:
        props = feature.get("properties", {}) or {}
        tooltip_text = " | ".join(f"{k}={v}" for k, v in props.items())
        popup_html = "<br>".join(
            f"<b>{k}</b> = {v}" for k, v in props.items()
        ) or "(no tags)"
        folium.GeoJson(
            feature,
            name=tooltip_text[:50] or "feature",
            style_function=lambda _f: {
                "color": "#3388ff",
                "weight": 2,
                "fillColor": "#3388ff",
                "fillOpacity": 0.2,
            },
            tooltip=tooltip_text or None,
            popup=folium.Popup(popup_html, max_width=300),
        ).add_to(folium_map)

    folium_map.fit_bounds([sw, ne])

    output_path.parent.mkdir(parents=True, exist_ok=True)
    folium_map.save(str(output_path))
