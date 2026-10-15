import json
from pathlib import Path

from osm_tags_to_object.map import compute_bounds, render_map


def _write_geojson(path: Path, features: list[dict]) -> None:
    path.write_text(json.dumps({"type": "FeatureCollection", "features": features}))


def _polygon_feature(coords: list[list[float]], props: dict, fid: int = 1) -> dict:
    # GeoJSON: coordinates are [lon, lat]
    ring = coords + [coords[0]]
    return {
        "type": "Feature",
        "id": fid,
        "osm_type": "way",
        "properties": props,
        "geometry": {"type": "Polygon", "coordinates": [ring]},
    }


def test_compute_bounds_returns_corners_of_all_features():
    features = [
        _polygon_feature([[7.0, 43.0], [7.1, 43.0], [7.1, 43.1]], {"amenity": "a"}),
        _polygon_feature([[8.0, 44.0], [8.2, 44.0], [8.2, 44.2]], {"amenity": "b"}),
    ]
    sw, ne = compute_bounds(features)
    # (lat, lon) order for folium
    assert sw == (43.0, 7.0)
    assert ne == (44.2, 8.2)


def test_compute_bounds_handles_features_without_geometry():
    features = [
        {"type": "Feature", "properties": {}, "geometry": None},
        _polygon_feature([[7.0, 43.0], [7.1, 43.0], [7.1, 43.1]], {}),
    ]
    sw, ne = compute_bounds(features)
    assert sw == (43.0, 7.0)
    assert ne == (43.1, 7.1)


def test_compute_bounds_raises_on_empty_input():
    import pytest

    with pytest.raises(ValueError):
        compute_bounds([])


def test_render_map_writes_an_html_file(tmp_path: Path):
    geojson = tmp_path / "in.geojson"
    html = tmp_path / "out.html"
    _write_geojson(
        geojson,
        [_polygon_feature([[7.0, 43.0], [7.1, 43.0], [7.1, 43.1]], {"amenity": "bench"})],
    )

    render_map(geojson, html)

    assert html.exists()
    text = html.read_text()
    # Leaflet / folium always produce an HTML document with these markers.
    assert "<html" in text.lower()
    assert "leaflet" in text.lower()


def test_render_map_embeds_feature_properties_as_tooltip(tmp_path: Path):
    geojson = tmp_path / "in.geojson"
    html = tmp_path / "out.html"
    _write_geojson(
        geojson,
        [
            _polygon_feature(
                [[7.0, 43.0], [7.1, 43.0], [7.1, 43.1]],
                {"amenity": "bench", "material": "wood"},
            )
        ],
    )

    render_map(geojson, html)

    text = html.read_text()
    assert "amenity" in text
    assert "bench" in text
    assert "material" in text
    assert "wood" in text
