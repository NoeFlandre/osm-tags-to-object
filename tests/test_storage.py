import json
from pathlib import Path

from osm_tags_to_object.models import OSMObject
from osm_tags_to_object.storage import write_objects


def _geom():
    return ((43.7, 7.4), (43.8, 7.5))


def test_write_objects_streams_to_geojson_file(tmp_path: Path):
    path = tmp_path / "out.geojson"
    objects = [
        OSMObject(type="way", id=1, tags={"amenity": "bench"}, geometry=_geom()),
        OSMObject(type="way", id=2, tags={"amenity": "fountain"}, geometry=_geom()),
    ]
    returned = write_objects(objects, path, format="geojson")

    assert returned == path
    data = json.loads(path.read_text())
    assert len(data["features"]) == 2


def test_write_objects_creates_parent_directories(tmp_path: Path):
    path = tmp_path / "nested" / "deeper" / "out.geojson"
    objects = [OSMObject(type="way", id=1, tags={"amenity": "bench"}, geometry=_geom())]
    write_objects(objects, path, format="geojson")
    assert path.exists()


def test_write_objects_to_parquet(tmp_path: Path):
    import pyarrow.parquet as pq

    path = tmp_path / "out.parquet"
    objects = [
        OSMObject(type="way", id=i, tags={"amenity": "bench"}, geometry=_geom())
        for i in range(3)
    ]
    write_objects(objects, path, format="parquet")
    assert pq.read_table(path).num_rows == 3


def test_write_objects_accepts_a_generator(tmp_path: Path):
    path = tmp_path / "out.geojson"

    def gen():
        for i in range(10):
            yield OSMObject(type="way", id=i, tags={"amenity": "bench"}, geometry=_geom())

    write_objects(gen(), path, format="geojson")
    assert len(json.loads(path.read_text())["features"]) == 10


def test_write_objects_rejects_unknown_format(tmp_path: Path):
    import pytest

    with pytest.raises(ValueError):
        write_objects([], tmp_path / "x.csv", format="csv")
