import json
from pathlib import Path

from osm_tags_to_object.formats.geojson import GeoJSONWriter
from osm_tags_to_object.models import OSMObject


def _read_json(path: Path) -> dict:
    return json.loads(path.read_text())


def test_geojson_writer_emits_a_featurecollection(tmp_path: Path):
    out = tmp_path / "out.geojson"
    with GeoJSONWriter(out) as w:
        w.write(OSMObject(type="way", id=1, tags={"amenity": "bench"}))

    data = _read_json(out)
    assert data["type"] == "FeatureCollection"
    assert isinstance(data["features"], list)


def test_geojson_writer_emits_one_feature_per_object(tmp_path: Path):
    out = tmp_path / "out.geojson"
    geom = ((43.73, 7.42), (43.74, 7.43), (43.75, 7.44))
    with GeoJSONWriter(out) as w:
        w.write(OSMObject(type="way", id=1, tags={"amenity": "bench"}, geometry=geom))
        w.write(OSMObject(type="way", id=2, tags={"amenity": "fountain"}, geometry=geom))

    data = _read_json(out)
    assert len(data["features"]) == 2
    assert {f["id"] for f in data["features"]} == {1, 2}


def test_geojson_writer_uses_lon_lat_order_in_geometry(tmp_path: Path):
    out = tmp_path / "out.geojson"
    geom = ((43.73, 7.42), (43.74, 7.43), (43.75, 7.44))
    with GeoJSONWriter(out) as w:
        w.write(OSMObject(type="way", id=1, tags={}, geometry=geom))

    feature = _read_json(out)["features"][0]
    # GeoJSON convention: coordinates are [lon, lat]
    assert feature["geometry"]["type"] == "Polygon"
    assert feature["geometry"]["coordinates"] == [
        [[7.42, 43.73], [7.43, 43.74], [7.44, 43.75], [7.42, 43.73]]
    ]


def test_geojson_writer_puts_tags_in_properties(tmp_path: Path):
    out = tmp_path / "out.geojson"
    with GeoJSONWriter(out) as w:
        w.write(
            OSMObject(
                type="way",
                id=1,
                tags={"amenity": "bench", "material": "wood"},
                geometry=((0.0, 0.0), (1.0, 0.0), (1.0, 1.0)),
            )
        )

    feature = _read_json(out)["features"][0]
    assert feature["properties"] == {"amenity": "bench", "material": "wood"}
    assert feature["id"] == 1
    assert feature["osm_type"] == "way"


def test_geojson_writer_skips_ways_with_no_geometry(tmp_path: Path):
    out = tmp_path / "out.geojson"
    with GeoJSONWriter(out) as w:
        w.write(OSMObject(type="way", id=1, tags={"amenity": "bench"}))

    assert _read_json(out)["features"] == []


def test_geojson_writer_closes_feature_list_properly(tmp_path: Path):
    out = tmp_path / "out.geojson"
    GeoJSONWriter(out).__enter__()
    Path(out).write_text("")

    out2 = tmp_path / "out2.geojson"
    w = GeoJSONWriter(out2)
    w.__enter__()
    w.write(OSMObject(type="way", id=1, tags={"a": "b"}, geometry=((0, 0), (1, 0), (0, 1))))
    w.__exit__(None, None, None)

    text = out2.read_text()
    assert text.rstrip().endswith("]}")
