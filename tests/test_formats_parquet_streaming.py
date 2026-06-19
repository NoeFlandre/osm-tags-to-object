import pyarrow.parquet as pq

from osm_tags_to_object.formats.parquet import ParquetWriter
from osm_tags_to_object.models import OSMObject


def _geom():
    return ((43.7, 7.4), (43.8, 7.5))


def test_parquet_writer_flushes_a_partial_row_group_on_close(tmp_path):
    out = tmp_path / "out.parquet"
    with ParquetWriter(out, row_group_size=100) as w:
        for i in range(7):
            w.write(OSMObject(type="way", id=i, tags={"amenity": "bench"}, geometry=_geom()))

    # All 7 rows present even though we never hit row_group_size.
    assert pq.read_table(out).num_rows == 7


def test_parquet_writer_creates_multiple_row_groups_when_buffer_overflows(tmp_path):
    out = tmp_path / "out.parquet"
    with ParquetWriter(out, row_group_size=5) as w:
        for i in range(12):
            w.write(
                OSMObject(
                    type="way", id=i, tags={"amenity": "bench"}, geometry=_geom()
                )
            )

    # 12 rows with row_group_size=5 -> at least 3 row groups (5+5+2).
    pf = pq.ParquetFile(out)
    assert pf.num_row_groups >= 3
    # Row counts across groups must sum to 12.
    assert sum(pf.metadata.row_group(i).num_rows for i in range(pf.num_row_groups)) == 12


def test_parquet_writer_with_row_group_size_one_writes_one_row_per_group(tmp_path):
    out = tmp_path / "out.parquet"
    with ParquetWriter(out, row_group_size=1) as w:
        for i in range(4):
            w.write(
                OSMObject(
                    type="way", id=i, tags={"amenity": "bench"}, geometry=_geom()
                )
            )

    pf = pq.ParquetFile(out)
    assert pf.num_row_groups == 4
    assert pq.read_table(out).num_rows == 4


def test_parquet_writer_empty_input_still_produces_a_valid_file(tmp_path):
    out = tmp_path / "out.parquet"
    with ParquetWriter(out, row_group_size=100):
        pass  # no writes

    # File is valid and has zero rows.
    assert pq.read_table(out).num_rows == 0


def test_parquet_writer_buffer_does_not_grow_beyond_row_group_size(tmp_path):
    """The in-memory buffer must not exceed row_group_size rows."""
    out = tmp_path / "out.parquet"
    w = ParquetWriter(out, row_group_size=5)
    w.__enter__()
    try:
        for i in range(20):
            w.write(OSMObject(type="way", id=i, tags={"amenity": "bench"}, geometry=_geom()))
            # After every write, buffer should be < row_group_size (a flush
            # empties it).
            assert len(w._buffer) < 5
    finally:
        w.__exit__(None, None, None)
