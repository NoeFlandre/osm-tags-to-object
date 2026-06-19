from pathlib import Path

import pyarrow.parquet as pq

from osm_tags_to_object.formats.parquet import ParquetWriter
from osm_tags_to_object.models import OSMObject


def _read_table(path: Path):
    return pq.read_table(path)


def test_parquet_writer_creates_a_readable_file(tmp_path: Path):
    out = tmp_path / "out.parquet"
    with ParquetWriter(out) as w:
        w.write(OSMObject(type="way", id=1, tags={"amenity": "bench"}))

    table = _read_table(out)
    assert table.num_rows == 1
    assert table.column("type").to_pylist() == ["way"]
    assert table.column("id").to_pylist() == [1]


def test_parquet_writer_persists_tags(tmp_path: Path):
    out = tmp_path / "out.parquet"
    with ParquetWriter(out) as w:
        w.write(
            OSMObject(
                type="way",
                id=1,
                tags={"amenity": "bench", "material": "wood"},
            )
        )

    tags = _read_table(out).column("tags").to_pylist()[0]
    assert dict(tags) == {"amenity": "bench", "material": "wood"}


def test_parquet_writer_persists_geometry(tmp_path: Path):
    out = tmp_path / "out.parquet"
    geom = ((43.73, 7.42), (43.74, 7.43))
    with ParquetWriter(out) as w:
        w.write(OSMObject(type="way", id=1, tags={}, geometry=geom))

    geometry = _read_table(out).column("geometry").to_pylist()[0]
    # pyarrow flattens structs in list<struct> into a list of dicts
    assert geometry == [{"lat": 43.73, "lon": 7.42}, {"lat": 43.74, "lon": 7.43}]


def test_parquet_writer_handles_missing_geometry(tmp_path: Path):
    out = tmp_path / "out.parquet"
    with ParquetWriter(out) as w:
        w.write(OSMObject(type="way", id=1, tags={"amenity": "bench"}))

    geometry = _read_table(out).column("geometry").to_pylist()[0]
    assert geometry is None or geometry == []


def test_parquet_writer_writes_multiple_objects(tmp_path: Path):
    out = tmp_path / "out.parquet"
    geom = ((43.7, 7.4), (43.8, 7.5))
    with ParquetWriter(out) as w:
        for i in range(5):
            w.write(
                OSMObject(
                    type="way",
                    id=i,
                    tags={"amenity": "bench"},
                    geometry=geom,
                )
            )

    assert _read_table(out).num_rows == 5
